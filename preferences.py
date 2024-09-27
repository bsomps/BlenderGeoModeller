import bpy

class GeoModellerPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__  

    use_scene_crs: bpy.props.BoolProperty(
        name="Use Scene CRS",
        description="Whether to use the Scene's Coordinate Reference System",
        default=True
    )
    
    use_z_descending: bpy.props.BoolProperty(
        name="Sort Drill Data Z Descending",  
        description="Sorts the CSV first by Z descending, then by hole_id",
        default=True
    )

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text="GeoModeller Preferences")
        col.prop(self, "use_scene_crs", text="Use Scene CRS")
        col.prop(self, "use_z_descending", text="Sort Drill Data Z Descending")

def get_preferences():
    return bpy.context.preferences.addons[__package__].preferences

def register_class(cls):
    try:
        bpy.utils.register_class(cls)
    except Exception as e:  
        print(f"Class {cls.__name__} is already registered, unregistering it first. Error: {e}")
        bpy.utils.unregister_class(cls)
        bpy.utils.register_class(cls)

def unregister_class(cls):
    try:
        bpy.utils.unregister_class(cls)
    except Exception as e:  
        print(f"Class {cls.__name__} was not registered, skipping unregister. Error: {e}")

def register():
    register_class(GeoModellerPreferences)

def unregister():
    unregister_class(GeoModellerPreferences)

if __name__ == "__main__":
    register()
