
bl_info = {
    "name": "Animation Merger",
    "author": "Yuan",
    "version": (1, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Animation Merger",
    "description": "Allows users to select actions, bones, and set influences, then merge to create a new action track",
    "category": "Animation",
}


import bpy

# Define a custom property group to store action, bone, and influence for each row
class MyAddonRow(bpy.types.PropertyGroup):
    action: bpy.props.StringProperty(
    name="Action",
    description="Choose an action"
    )
    bone: bpy.props.EnumProperty(
        name="Bone",
        description="Choose a bone",
        items=lambda self, context: get_bones(self, context)
    )
    influence: bpy.props.FloatProperty(
        name="Influence",
        description="Set influence",
        default=1.0,  # Default influence value
        min=0.0,      # Minimum influence value
        max=1.0       # Maximum influence value
    )
    nla_strip_name: bpy.props.StringProperty(
        name="Baked NLA Name",
        description="Name of the new baked NLA strip",
        default="Baked_Action"
    )


class MyAddonPanel(bpy.types.Panel):
    """Creates a Panel in the 3D View"""
    bl_label = "Animation Merger"
    bl_idname = "OBJECT_PT_my_addon_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Animation Merger'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        # Draw each row from the collection
        for i, row_data in enumerate(scene.my_addon_rows):
            draw_row(self, context, layout, row_data, i)

        # Button to add a new row
        layout.operator("addon.add_row", text="Add Row")

        # Button to apply the action to bones
        layout.operator("addon.apply_action_to_bones", text="Apply Action")
        
        # Row for the NLA bake button and name entry
        row = layout.row()
        row.prop(scene, "merged_action_name", text="Merged Name")  # 
        row.operator("addon.merge_nla_strips", text="Merge Action Strips")     # Bake Button


# Function to draw a single row (Action, Bone, and Influence Selector, plus delete button)
def draw_row(self, context, layout, row_data, row_index):  
    obj = context.object
    row = layout.row()
    
    # First Scroll: Action Selector (unique for each row)
    row.prop_search(row_data, "action", bpy.data, "actions", text="Action")
    
    # Second Scroll: Bone Selector (only if object is an armature, unique per row)
    if obj and obj.type == 'ARMATURE':
        row.prop(row_data, "bone", text="Bone")
    else:
        row.label(text="No armature selected.")
    
    # Influence Slider: Float Property (0 to 1)
    row.prop(row_data, "influence", text="Influence")
    
    # Add a Delete Row button for each row
    row.operator("addon.delete_row", text="Delete").row_index = row_index
    
    
def duplicate_action(action):
    """Creates a duplicate of the given action"""
    new_action = action.copy()
    new_action.name = action.name + "_copy" 
    return new_action

def check_and_add_animation_track(obj, action_name, bone_name, influence, used_bones):
    original_action = bpy.data.actions.get(action_name)
    
    # Duplicate the action to prevent modifying the original
    action_copy = duplicate_action(original_action)
    
    if not obj.animation_data:
        obj.animation_data_create()

    obj.animation_data.action = action_copy
    fcurves = obj.animation_data.action.fcurves
    
    # Mute or unmute the fcurves based on bone hierarchy
    for fcurve in fcurves:
        fcurve_bone_name = fcurve.data_path.split('"')[1]
        if any(bone.name == fcurve_bone_name for bone in used_bones):
            fcurve.mute = False  # Unmute if bone is in the hierarchy
        else:
            fcurve.mute = True 
    
    # Add the duplicated action to the NLA track
    start_frame = 0 
    nla_track = obj.animation_data.nla_tracks.new()
    nla_strip = nla_track.strips.new(action_copy.name, start_frame, action_copy)
    
    # Set the influence of the NLA strip
    nla_strip.influence = influence
    nla_strip.use_animated_influence = True

    # Optionally, remove the active action to ensure the action is driven by the NLA strip
    obj.animation_data.action = None
    
     # Select the newly created track
    for track in obj.animation_data.nla_tracks:
        track.select = False  # Deselect all tracks
    nla_track.select = True  # Select the new track

    # 🔹 Save current area type
    current_area = bpy.context.area.type

    bpy.context.area.type = 'NLA_EDITOR'  # Switch area type
    bpy.ops.anim.channels_move(direction='BOTTOM')  # Move strip to bottom

    bpy.context.area.type = current_area

def append_list_bone_hierarchy(bone, bone_list, level=0):
    """Recursively append bone and its children to the bone_list"""
    bone_list.append(bone)
    for child_bone in bone.children:
        append_list_bone_hierarchy(child_bone, bone_list, level + 1)

# Operator to add a new row
class ADDON_OT_AddRow(bpy.types.Operator):
    """Add a new row"""
    bl_idname = "addon.add_row"
    bl_label = "Add Row"

    def execute(self, context):
        # Add a new entry to the collection
        context.scene.my_addon_rows.add()
        return {'FINISHED'}

# Operator to delete a row
class ADDON_OT_DeleteRow(bpy.types.Operator):
    """Delete a row"""
    bl_idname = "addon.delete_row"
    bl_label = "Delete Row"
    
    row_index: bpy.props.IntProperty()  # Store the index of the row to delete
    
    def execute(self, context):
        # Remove the entry from the collection
        context.scene.my_addon_rows.remove(self.row_index)
        return {'FINISHED'}


# Operator to apply actions and influence to selected bones
class ADDON_OT_ApplyActionToBones(bpy.types.Operator):
    """Apply action to bones based on user selection"""
    bl_idname = "addon.apply_action_to_bones"
    bl_label = "Apply Action to Bones"

    def execute(self, context):
        scene = context.scene
        obj = context.object
        
        # Loop through each row and apply the action and influence
        for row_data in scene.my_addon_rows:
            action_name = row_data.action
            bone_name = row_data.bone
            influence = row_data.influence
            
            # Initialize the list of used bones
            used_bones = []
            
            # Append the selected bone and its hierarchy
            if obj and obj.type == 'ARMATURE':
                for bone in obj.pose.bones:
                    if bone.name == bone_name:
                        append_list_bone_hierarchy(bone, used_bones)
            
            # Apply the action to the selected bones
            check_and_add_animation_track(obj, action_name, bone_name, influence, used_bones)
        
        return {'FINISHED'}
    
class ADDON_OT_MergeNLAStrips(bpy.types.Operator):
    """Merge all action strips into a single action"""
    bl_idname = "addon.merge_nla_strips"
    bl_label = "Merge NLA Strips"

    def execute(self, context):
        obj = context.object
        scene = context.scene
        merged_name = scene.merged_action_name  # Get user-defined name

        if not obj or obj.type != 'ARMATURE' or not obj.animation_data or not obj.animation_data.nla_tracks:
            self.report({'WARNING'}, "No armature with NLA tracks found")
            return {'CANCELLED'}

        # Create a new action to store baked data
        merged_action = bpy.data.actions.new(name=merged_name)
        obj.animation_data.action = merged_action  # Set as active action

        # Bake the NLA strips into the new action
        bpy.ops.nla.bake(
            frame_start=1,           # Start frame for baking
            frame_end=250,           # End frame for baking
            step=1,                  # Step size for baking (default is 1 frame)
            only_selected=False,     # Bake only selected bones (for armatures)
            visual_keying=True,      # Capture final visual transforms (important for constraints)
            clear_constraints=True, # Remove constraints after baking
            clear_parents=True,     # Remove parenting effects after baking
            use_current_action=False,# Bake all NLA tracks (False) or just the active action (True)
            clean_curves=False,
            bake_types={'POSE'},      # What to bake ('POSE', 'OBJECT', 'LOC', 'ROT', 'SCALE', etc.)
            channel_types={'LOCATION', 'ROTATION', 'SCALE', 'BBONE', 'PROPS'}
        )

        # Remove NLA tracks after merging
        for track in obj.animation_data.nla_tracks:
            obj.animation_data.nla_tracks.remove(track)
        
        return {'FINISHED'}

# Register the properties and operators globally
def register():
    bpy.utils.register_class(MyAddonPanel)
    bpy.utils.register_class(ADDON_OT_AddRow)
    bpy.utils.register_class(ADDON_OT_DeleteRow)
    bpy.utils.register_class(ADDON_OT_ApplyActionToBones)
    bpy.utils.register_class(MyAddonRow)
    bpy.utils.register_class(ADDON_OT_MergeNLAStrips)
    bpy.types.Scene.merged_action_name = bpy.props.StringProperty(  
        name="Merged Action Name",
        description="Name for the merged action strip",
        default="Merged_Action"
    )
    
    # Create a collection property to store the rows
    bpy.types.Scene.my_addon_rows = bpy.props.CollectionProperty(type=MyAddonRow)

def unregister():
    del bpy.types.Scene.my_addon_rows
    del bpy.types.Scene.merged_action_name  # 
    bpy.utils.unregister_class(MyAddonPanel)
    bpy.utils.unregister_class(ADDON_OT_AddRow)
    bpy.utils.unregister_class(ADDON_OT_DeleteRow)
    bpy.utils.unregister_class(ADDON_OT_ApplyActionToBones)
    bpy.utils.unregister_class(MyAddonRow)
    bpy.utils.unregister_class(ADDON_OT_MergeNLAStrips)


# Functions to get available actions and bones
def get_actions(self, context):
    return sorted([(action.name, action.name, "") for action in bpy.data.actions], key=lambda a: a[0])

def get_bones(self, context):
    obj = context.object
    if obj and obj.type == 'ARMATURE':
        return [(bone.name, bone.name, "") for bone in obj.data.bones]
    return []


if __name__ == "__main__":
    register()
