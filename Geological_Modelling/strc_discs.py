import bpy
import bmesh
from math import radians

def get_unique_properties(collection):
    unique_props = set()
    for obj in collection.all_objects:
        for key in obj.keys():
            if key not in {'_RNA_UI', 'cycles'}:
                unique_props.add(key)
    return list(unique_props)

def update_properties_list(self, context):
    props = context.scene.structural_discs_tool
    collection = bpy.data.collections.get(props.collection_name)
    if collection:
        props.available_properties.clear()
        sorted_properties = sorted(get_unique_properties(collection))
        for prop in sorted_properties:
            item = props.available_properties.add()
            item.name = prop

def get_properties_items(self, context):
    return [(prop.name, prop.name, "") for prop in context.scene.structural_discs_tool.available_properties]

class StructuralDiscsProperties(bpy.types.PropertyGroup):
    collection_name: bpy.props.StringProperty(name="Collection Name", update=update_properties_list)
    available_properties: bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)
    strike_property: bpy.props.EnumProperty(name="Strike Property", items=get_properties_items)
    dip_property: bpy.props.EnumProperty(name="Dip Property", items=get_properties_items)
    size: bpy.props.FloatProperty(name="Size", description="Size of the discs", default=5.0, min=0.1, max=1000.0)
    orientation_mode: bpy.props.EnumProperty(
        name="Orientation Mode",
        description="Choose the orientation mode for strike and dip",
        items=[
            ('DIP_DIRECTION', "Dip Direction", "Use dip direction for strike and dip"),
            ('RIGHT_HAND_RULE', "Right Hand Rule", "Use right hand rule for strike and dip")
        ],
        default='DIP_DIRECTION'
    )

class IMPORT_PT_panel_structural_discs(bpy.types.Panel):
    bl_label = "Structural Discs"
    bl_idname = "IMPORT_PT_panel_structural_discs"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'GeoModeller'  
    bl_parent_id = "GEOMOD_PT_geologic_models_category"  
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.structural_discs_tool

        layout.prop_search(props, "collection_name", bpy.data, "collections", text="Choose Collection")
        layout.prop(props, "strike_property")
        layout.prop(props, "dip_property")
        layout.prop(props, "size")
        layout.prop(props, "orientation_mode", expand=True)
        layout.operator("import_collection.structural_discs", text="Generate Structural Discs", icon='PLAY')

def create_disc_mesh(radius, name):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=True, radius=radius, segments=32)
    bm.to_mesh(mesh)
    bm.free()
    return mesh

def create_disc_object(location, rotation, scale, name, mesh, collection, source_obj):
    disc = bpy.data.objects.new(name, mesh)
    disc.location = location
    disc.rotation_euler = rotation
    disc.scale = scale
    
    # Copy custom properties
    for key, value in source_obj.items():
        if key not in {'_RNA_UI', 'cycles'}:
            disc[key] = value

    collection.objects.link(disc)
    return disc

def make_mesh_unique(obj):
    # Make a unique copy of the object's mesh
    mesh = obj.data.copy()
    mesh.name = f"{obj.name}_Mesh"
    obj.data = mesh

class IMPORT_OT_generate_structural_discs(bpy.types.Operator):
    bl_idname = "import_collection.structural_discs"
    bl_label = "Generate Structural Discs"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            props = context.scene.structural_discs_tool
            collection = bpy.data.collections.get(props.collection_name)

            if not collection:
                self.report({'ERROR'}, "Collection not found.")
                return {'CANCELLED'}

            # Create a template mesh for the discs
            template_mesh = create_disc_mesh(radius=25.0, name="TemplateDiscMesh")

            # Create a new collection for the discs
            discs_collection_name = "Structural Discs Collection"
            discs_collection = bpy.data.collections.new(discs_collection_name)
            bpy.context.scene.collection.children.link(discs_collection)

            skipped_count = 0  # Counter for skipped objects

            for obj in collection.all_objects:
                if obj.type in {'MESH', 'CURVE'}:
                    try:
                        strike_prop = obj.get(props.strike_property, None)
                        dip_prop = obj.get(props.dip_property, None)
                        if strike_prop is None or dip_prop is None:
                            continue
                        strike = float(strike_prop)
                        dip = float(dip_prop)

                        # Skip objects with invalid strike or dip
                        if not (0 <= strike <= 360) or dip > 90:
                            skipped_count += 1
                            continue
                    except (TypeError, ValueError):
                        continue

                    if obj.type == 'CURVE':
                        curve = obj.data
                        if curve.splines and len(curve.splines[0].points) >= 2:
                            spline = curve.splines[0]
                            points = spline.points if hasattr(spline, 'points') else spline.bezier_points
                            low_point = min(points, key=lambda p: p.co.z)
                            coords = low_point.co[:3]  # Ignore the 'w' for NURBS
                        else:
                            continue
                    elif obj.type == 'MESH' and len(obj.data.vertices) > 0:
                        coords = obj.location  
                    else:
                        continue

                    # Calculate rotation
                    if props.orientation_mode == 'RIGHT_HAND_RULE':
                        strike = (strike + 90) % 360
                    rotation = (radians(dip), 0, radians(-(strike + 180)))

                    # Create and link the disc object
                    disc = create_disc_object(location=coords, rotation=rotation, scale=(props.size, props.size, props.size),
                                              name=obj.name, mesh=template_mesh, collection=discs_collection, source_obj=obj)

                    # Make the disc's mesh unique
                    make_mesh_unique(disc)

            # Report the number of skipped objects
            if skipped_count > 0:
                self.report({'INFO'}, f"{skipped_count} objects were skipped due to invalid strike or dip values.")

            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


def register():
    bpy.utils.register_class(StructuralDiscsProperties)
    bpy.utils.register_class(IMPORT_PT_panel_structural_discs)
    bpy.utils.register_class(IMPORT_OT_generate_structural_discs)

    bpy.types.Scene.structural_discs_tool = bpy.props.PointerProperty(type=StructuralDiscsProperties)

def unregister():
    bpy.utils.unregister_class(StructuralDiscsProperties)
    bpy.utils.unregister_class(IMPORT_PT_panel_structural_discs)
    bpy.utils.unregister_class(IMPORT_OT_generate_structural_discs)

    del bpy.types.Scene.structural_discs_tool

if __name__ == "__main__":
    register()
