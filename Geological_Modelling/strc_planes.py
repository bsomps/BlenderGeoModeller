
import bpy
import bmesh
from math import radians
from mathutils import Vector

def get_unique_properties(collection):
    unique_props = set()
    for obj in collection.all_objects:
        for key in obj.keys():
            if key not in {'_RNA_UI', 'cycles'}:
                unique_props.add(key)
    return list(unique_props)

def update_properties_list(self, context):
    props = context.scene.structural_planes_tool
    collection = bpy.data.collections.get(props.collection_name)
    if collection:
        props.available_properties.clear()
        sorted_properties = sorted(get_unique_properties(collection))
        for prop in sorted_properties:
            item = props.available_properties.add()
            item.name = prop

def get_properties_items(self, context):
    return [(prop.name, prop.name, "") for prop in context.scene.structural_planes_tool.available_properties]

class StructuralPlanesProperties(bpy.types.PropertyGroup):
    collection_name: bpy.props.StringProperty(name="Collection Name", update=update_properties_list)
    available_properties: bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)
    strike_property: bpy.props.EnumProperty(name="Strike Property", items=get_properties_items)
    dip_property: bpy.props.EnumProperty(name="Dip Property", items=get_properties_items)
    bounding_box_object: bpy.props.PointerProperty(name="Bounding Box Object", type=bpy.types.Object)
    orientation_mode: bpy.props.EnumProperty(
        name="Orientation Mode",
        description="Choose the orientation mode for strike and dip",
        items=[
            ('DIP_DIRECTION', "Dip Direction", "Use dip direction for strike and dip"),
            ('RIGHT_HAND_RULE', "Right Hand Rule", "Use right hand rule for strike and dip")
        ],
        default='DIP_DIRECTION'
    )

class IMPORT_PT_panel_structural_planes(bpy.types.Panel):
    bl_label = "Structural Planes"
    bl_idname = "IMPORT_PT_panel_structural_planes"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'GeoModeller'  
    bl_parent_id = "GEOMOD_PT_geologic_models_category"  
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.structural_planes_tool

        layout.prop_search(props, "collection_name", bpy.data, "collections", text="Choose Collection")
        layout.prop(props, "strike_property")
        layout.prop(props, "dip_property")
        layout.prop(props, "bounding_box_object")
        layout.prop(props, "orientation_mode", expand=True)
        layout.operator("import_collection.structural_planes", text="Generate Structural Planes", icon='PLAY')

def create_plane_mesh(size, name):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size)
    bm.to_mesh(mesh)
    bm.free()
    return mesh

def create_plane_object(location, rotation, name, mesh, collection, source_obj):
    plane = bpy.data.objects.new(name, mesh)
    plane.location = location
    plane.rotation_euler = rotation
    
    # Copy custom properties
    for key, value in source_obj.items():
        if key not in {'_RNA_UI', 'cycles'}:
            plane[key] = value

    collection.objects.link(plane)
    return plane

class IMPORT_OT_generate_structural_planes(bpy.types.Operator):
    bl_idname = "import_collection.structural_planes"
    bl_label = "Generate Structural Planes"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            props = context.scene.structural_planes_tool
            collection = bpy.data.collections.get(props.collection_name)
            bounding_obj = props.bounding_box_object

            if not collection:
                self.report({'ERROR'}, "Collection not found.")
                return {'CANCELLED'}
            if not bounding_obj:
                self.report({'ERROR'}, "No bounding box object selected.")
                return {'CANCELLED'}

            # Determine the bounding box size in world coordinates
            bbox_corners = [bounding_obj.matrix_world @ Vector(corner) for corner in bounding_obj.bound_box]
            bbox_min = Vector((min(corner.x for corner in bbox_corners),
                               min(corner.y for corner in bbox_corners),
                               min(corner.z for corner in bbox_corners)))
            bbox_max = Vector((max(corner.x for corner in bbox_corners),
                               max(corner.y for corner in bbox_corners),
                               max(corner.z for corner in bbox_corners)))
            bbox_size = bbox_max - bbox_min
            plane_size = bbox_size.length * 1.2

            collection_planes = bpy.data.collections.new("structural planes")
            bpy.context.scene.collection.children.link(collection_planes)

            for obj in collection.all_objects:
                if obj.type in {'MESH', 'CURVE'}:
                    try:
                        strike_prop = obj.get(props.strike_property, None)
                        dip_prop = obj.get(props.dip_property, None)
                        if strike_prop is None or dip_prop is None:
                            continue
                        strike = float(strike_prop)
                        dip = float(dip_prop)
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

                    if props.orientation_mode == 'RIGHT_HAND_RULE':
                        strike = (strike + 90) % 360
                    rotation = (radians(dip), 0, radians(-(strike + 180)))

                    mesh = create_plane_mesh(plane_size, obj.name)
                    plane = create_plane_object(location=coords, rotation=rotation, name=obj.name, mesh=mesh, collection=collection_planes, source_obj=obj)
                    bpy.context.view_layer.objects.active = plane

                    # Perform boolean clipping
                    modifier = plane.modifiers.new(name="Boolean", type='BOOLEAN')
                    modifier.operation = 'INTERSECT'
                    modifier.solver = 'FAST'
                    modifier.use_self = True  # Enable Self Intersection
                    modifier.object = bounding_obj
                    

        except Exception as e:
            self.report({'ERROR'}, f"Unexpected error: {e}")
            return {'CANCELLED'}

        return {'FINISHED'}

def register():
    bpy.utils.register_class(StructuralPlanesProperties)
    bpy.utils.register_class(IMPORT_PT_panel_structural_planes)
    bpy.utils.register_class(IMPORT_OT_generate_structural_planes)

    bpy.types.Scene.structural_planes_tool = bpy.props.PointerProperty(type=StructuralPlanesProperties)

def unregister():
    bpy.utils.unregister_class(StructuralPlanesProperties)
    bpy.utils.unregister_class(IMPORT_PT_panel_structural_planes)
    bpy.utils.unregister_class(IMPORT_OT_generate_structural_planes)

    del bpy.types.Scene.structural_planes_tool

if __name__ == "__main__":
    register()
