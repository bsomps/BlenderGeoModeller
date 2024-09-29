
import bpy
import bmesh
import numpy as np
from scipy.interpolate import Rbf
from skimage.measure import marching_cubes
from mathutils import Vector
from scipy.spatial.distance import pdist

def get_unique_properties(collection):
    unique_props = set()
    for obj in collection.all_objects:
        for key in obj.keys():
            if key not in {'_RNA_UI', 'cycles'}:
                unique_props.add(key)
    return list(unique_props)

def update_properties_list(self, context):
    props = context.scene.grade_shell_tool
    collection = bpy.data.collections.get(props.collection_name)
    if collection:
        props.available_properties.clear()
        sorted_properties = sorted(get_unique_properties(collection))
        for prop in sorted_properties:
            item = props.available_properties.add()
            item.name = prop

def get_properties_items(self, context):
    return [(prop.name, prop.name, "") for prop in context.scene.grade_shell_tool.available_properties]

def calculate_default_epsilon(x, y, z):
    if len(x) < 2:
        return 1.0  # Default value if there are not enough points to calculate distances
    coords = np.vstack((x, y, z)).T
    distances = pdist(coords)
    return np.mean(distances)

class GradeShellProperties(bpy.types.PropertyGroup):
    collection_name: bpy.props.StringProperty(name="Collection Name", update=update_properties_list)
    available_properties: bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)
    data_property: bpy.props.EnumProperty(name="Data Property", items=get_properties_items)
    bounding_box_object: bpy.props.PointerProperty(name="Bounding Box Object", type=bpy.types.Object)
    cut_off_value: bpy.props.FloatProperty(name="Isosurface Value", default=0.0)
    grid_size: bpy.props.IntProperty(name="Grid Size", default=50, min=1)
    rbf_function: bpy.props.EnumProperty(
        name="RBF Function",
        items=[
            ('multiquadric', "Multiquadric", ""),
            ('inverse', "Inverse Multiquadric", ""),
            ('gaussian', "Gaussian", ""),
            ('linear', "Linear", ""),
            ('cubic', "Cubic", ""),
            ('quintic', "Quintic", ""),
            ('thin_plate', "Thin Plate Spline", "")
        ],
        default='linear'
    )
    epsilon_value: bpy.props.FloatProperty(name="Epsilon", default=1.0)

class IMPORT_PT_panel_grade_shell_mesh(bpy.types.Panel):
    bl_label = "RBF Grade Shell Mesh"
    bl_idname = "IMPORT_PT_panel_grade_shell_mesh"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'GeoModeller'
    bl_parent_id = "GEOMOD_PT_numerical_models_category"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.grade_shell_tool

        layout.prop_search(props, "collection_name", bpy.data, "collections", text="Choose Collection")
        layout.prop(props, "data_property")
        layout.prop(props, "cut_off_value")
        layout.prop(props, "bounding_box_object")
        layout.prop(props, "grid_size")
        layout.prop(props, "rbf_function")
        layout.prop(props, "epsilon_value")

        layout.operator("mesh.collection_mesh_generate_grade_shell", text="Generate Grade Shell Mesh", icon='PLAY')

class IMPORT_OT_generate_grade_shell_mesh(bpy.types.Operator):
    bl_idname = "mesh.collection_mesh_generate_grade_shell"
    bl_label = "Generate Grade Shell Mesh"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            props = context.scene.grade_shell_tool
            collection = bpy.data.collections.get(props.collection_name)
            bounding_obj = props.bounding_box_object

            if not collection:
                self.report({'ERROR'}, "Collection not found.")
                return {'CANCELLED'}
            if not bounding_obj:
                self.report({'ERROR'}, "No bounding box object selected.")
                return {'CANCELLED'}

            x, y, z, d = [], [], [], []

            for obj in collection.all_objects:
                if props.data_property not in obj.keys():
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

                # Ensures the data is convertible to float before appending
                try:
                    d_value = float(obj[props.data_property])
                    
                    x.append(coords[0])
                    y.append(coords[1])
                    z.append(coords[2])
                    d.append(d_value)
                except (ValueError, TypeError):
                    self.report({'WARNING'}, f"Skipping object {obj.name} due to non-numeric data.")
                    continue

            if not x:
                self.report({'ERROR'}, "No valid data points found in the collection.")
                return {'CANCELLED'}

            bbox_corners = [bounding_obj.matrix_world @ Vector(corner) for corner in bounding_obj.bound_box]
            bbox_min = Vector((min(corner.x for corner in bbox_corners),
                               min(corner.y for corner in bbox_corners),
                               min(corner.z for corner in bbox_corners)))
            bbox_max = Vector((max(corner.x for corner in bbox_corners),
                               max(corner.y for corner in bbox_corners),
                               max(corner.z for corner in bbox_corners)))

            filtered_x, filtered_y, filtered_z, filtered_d = [], [], [], []
            for xi, yi, zi, di in zip(x, y, z, d):
                if (bbox_min.x <= xi <= bbox_max.x and
                    bbox_min.y <= yi <= bbox_max.y and
                    bbox_min.z <= zi <= bbox_max.z):
                    filtered_x.append(xi)
                    filtered_y.append(yi)
                    filtered_z.append(zi)
                    filtered_d.append(di)
            
            if not filtered_x:
                self.report({'ERROR'}, "No valid data points within the bounding box.")
                return {'CANCELLED'}

            if props.epsilon_value == 1.0:  # Default value, calculate average distance, doesnt work as expected
                props.epsilon_value = calculate_default_epsilon(filtered_x, filtered_y, filtered_z)

            rbf = Rbf(filtered_x, filtered_y, filtered_z, filtered_d, function=props.rbf_function, epsilon=props.epsilon_value, smooth=0.1)
            grid_x, grid_y, grid_z = np.mgrid[bbox_min.x:bbox_max.x:props.grid_size*1j,
                                              bbox_min.y:bbox_max.y:props.grid_size*1j,
                                              bbox_min.z:bbox_max.z:props.grid_size*1j]
            scalar_field = rbf(grid_x, grid_y, grid_z)

            self.report({'INFO'}, "RBF interpolation completed successfully.")
            
            spacing_x = (bbox_max.x - bbox_min.x) / (props.grid_size - 1)
            spacing_y = (bbox_max.y - bbox_min.y) / (props.grid_size - 1)
            spacing_z = (bbox_max.z - bbox_min.z) / (props.grid_size - 1)
            spacing = (spacing_x, spacing_y, spacing_z)

            verts, faces, _, _ = marching_cubes(scalar_field, level=props.cut_off_value, spacing=spacing)
            verts_offset = [(v[0] + bbox_min.x, v[1] + bbox_min.y, v[2] + bbox_min.z) for v in verts]

            mesh = bpy.data.meshes.new("InterpolatedMesh")
            mesh.from_pydata(verts_offset, [], faces.tolist())
            mesh.update()

            obj = bpy.data.objects.new(f"{props.data_property}_Interpolant", mesh)
            
            # object is linked directly to the scene collection
            scene_collection = bpy.context.scene.collection
            scene_collection.objects.link(obj)

            self.report({'INFO'}, "Mesh generated and added to the scene.")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Unexpected error: {e}")
            return {'CANCELLED'}
        
classes = [
    GradeShellProperties,
    IMPORT_OT_generate_grade_shell_mesh,
    IMPORT_PT_panel_grade_shell_mesh
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Scene.grade_shell_tool = bpy.props.PointerProperty(type=GradeShellProperties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    del bpy.types.Scene.grade_shell_tool

if __name__ == "__main__":
    register()
