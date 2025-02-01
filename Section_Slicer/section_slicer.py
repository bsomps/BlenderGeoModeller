import bpy

class SlicerSettings(bpy.types.PropertyGroup):
    apply_default_slicer: bpy.props.BoolProperty(
        name="Apply Default Slicer", 
        default=False, 
        update=lambda self, context: slicer_toggle(self, context)
    )
    use_custom_object: bpy.props.BoolProperty(
        name="Use Custom Object", 
        default=False, 
        update=lambda self, context: slicer_toggle(self, context)
    )
    boolean_type: bpy.props.EnumProperty(
        name="Boolean Type",
        description="Choose the type of boolean operation",
        items=[
            ('FAST', "Fast", "Fast boolean operation"),
            ('EXACT', "Exact", "Exact boolean operation"),
        ],
        default='EXACT',
        update=lambda self, context: update_boolean_type(self.boolean_type)
    )
    slicing_object: bpy.props.PointerProperty(
        name="Slicing Object",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
        update=lambda self, context: update_slicing_object(self, context)  # Add update callback
    )

def create_slicer_cube():
    cursor_location = bpy.context.scene.cursor.location
    bpy.ops.mesh.primitive_cube_add(size=2, location=cursor_location)
    slicer_cube = bpy.context.active_object
    slicer_cube.name = "SlicerCube"
    slicer_cube.display_type = 'WIRE'
    slicer_cube.scale = (2500, 50, 1000)  # default dimensions
    
    # Ensure the slicer cube is not in any collection
    for collection in slicer_cube.users_collection:
        collection.objects.unlink(slicer_cube)
    
    # Link slicer cube directly to the scene
    bpy.context.scene.collection.objects.link(slicer_cube)
    
    return slicer_cube

def get_visible_mesh_objects():
    visible_mesh_objects = []
    for obj in bpy.context.view_layer.objects:
        if obj.type == 'MESH' and obj.visible_get():
            visible_mesh_objects.append(obj)
    return visible_mesh_objects

def update_slicing_object(self, context):
    """Update boolean modifiers when the slicing object is changed."""
    if self.use_custom_object and self.slicing_object:
        print(f"Slicing object updated to: {self.slicing_object.name}")
        update_boolean_modifiers(self.slicing_object)

def slicer_toggle(self, context):
    if self.apply_default_slicer and self.use_custom_object:
        if self == context.scene.slicer_settings.use_custom_object:
            self.apply_default_slicer = False
        else:
            self.use_custom_object = False
    
    if self.apply_default_slicer:
        slicer_cube = create_slicer_cube()
        context.scene.slicer_settings.slicing_object = slicer_cube
        update_boolean_modifiers(slicer_cube)
    elif self.use_custom_object:
        slicing_object = context.scene.slicer_settings.slicing_object
        if slicing_object:
            print(f"Using custom slicing object: {slicing_object.name}")
            update_boolean_modifiers(slicing_object)
        else:
            print("No custom slicing object selected")
    else:
        remove_slicer()

def update_boolean_modifiers(slicing_object):
    boolean_type = bpy.context.scene.slicer_settings.boolean_type
    visible_mesh_objects = get_visible_mesh_objects()
    for obj in visible_mesh_objects:
        # Skip if the object is the same as the slicing object to avoid circular reference
        if obj == slicing_object:
            continue
        boolean_modifier = obj.modifiers.get("SlicerBoolean")
        if not boolean_modifier:
            boolean_modifier = obj.modifiers.new(name="SlicerBoolean", type='BOOLEAN')
        boolean_modifier.object = slicing_object
        boolean_modifier.operation = 'INTERSECT'
        boolean_modifier.solver = boolean_type

        if boolean_type == 'EXACT':
            boolean_modifier.use_self = True
            boolean_modifier.use_hole_tolerant = True

        print(f"Updated boolean modifier for {obj.name} with slicing object {slicing_object.name}")

def remove_slicer():
    slicer_cube = bpy.data.objects.get("SlicerCube")
    if slicer_cube:
        bpy.data.objects.remove(slicer_cube)
    for obj in bpy.context.scene.objects:
        for modifier in obj.modifiers:
            if modifier.type == 'BOOLEAN' and modifier.name == "SlicerBoolean":
                obj.modifiers.remove(modifier)

def update_boolean_type(boolean_type):
    slicing_object = bpy.context.scene.slicer_settings.slicing_object
    if slicing_object:
        update_boolean_modifiers(slicing_object)

class SlicerPanel(bpy.types.Panel):
    bl_label = "Section Slicer"
    bl_idname = "GEOMOD_PT_section_slicer"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'GeoModeller'
    bl_options = {'DEFAULT_CLOSED'}    

    def draw(self, context):
        layout = self.layout
        slicer_settings = context.scene.slicer_settings

        layout.prop(slicer_settings, "apply_default_slicer")
        layout.prop(slicer_settings, "use_custom_object")
        layout.prop(slicer_settings, "boolean_type")
        
        if slicer_settings.use_custom_object:
            layout.prop_search(slicer_settings, "slicing_object", context.scene, "objects")

classes = [
    SlicerSettings,
    SlicerPanel
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Scene.slicer_settings = bpy.props.PointerProperty(type=SlicerSettings)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    props = [
        'slicer_settings'
    ]
    
    for prop in props:
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)

if __name__ == "__main__":
    register()
