import bpy
import bmesh
import numpy as np
from scipy.interpolate import Rbf
from mathutils import Vector
import matplotlib.pyplot as plt
from scipy.spatial.distance import pdist

def get_unique_properties(collection):
    unique_props = set()
    for obj in collection.all_objects:
        for key in obj.keys():
            if key not in {'_RNA_UI', 'cycles'}:
                unique_props.add(key)
    return list(unique_props)

def update_properties_list(self, context):
    props = context.scene.interpolated_volume_tool
    collection = bpy.data.collections.get(props.collection_name)
    if collection:
        props.available_properties.clear()
        sorted_properties = sorted(get_unique_properties(collection))
        for prop in sorted_properties:
            item = props.available_properties.add()
            item.name = prop

def get_properties_items(self, context):
    return [(prop.name, prop.name, "") for prop in context.scene.interpolated_volume_tool.available_properties]

def calculate_default_epsilon(x, y, z):
    if len(x) < 2:
        return 1.0  # Default value if there are not enough points to calculate distances
    coords = np.vstack((x, y, z)).T
    distances = pdist(coords)
    return np.mean(distances)

class InterpolatedVolumeProperties(bpy.types.PropertyGroup):
    collection_name: bpy.props.StringProperty(name="Collection Name", update=update_properties_list)
    available_properties: bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)
    data_property: bpy.props.EnumProperty(name="Data Property", items=get_properties_items)
    bounding_box_object: bpy.props.PointerProperty(name="Bounding Box Object", type=bpy.types.Object)
    grid_size: bpy.props.IntProperty(name="Grid Size", default=10, min=1)
    normalize_colormap: bpy.props.BoolProperty(name="Normalize Colormap", default=False)
    iqr_scaling_factor: bpy.props.FloatProperty(name="IQR Scaling Factor", default=3.0, min=0.0, max=100.0)
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

class IMPORT_PT_panel_interpolated_block(bpy.types.Panel):
    bl_label = "RBF Interpolated Block Model"
    bl_idname = "IMPORT_PT_panel_interpolated_block"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'GeoModeller'
    bl_parent_id = "GEOMOD_PT_numerical_models_category"
    bl_options = {'DEFAULT_CLOSED'}
  

    def draw(self, context):
        layout = self.layout
        props = context.scene.interpolated_volume_tool

        layout.prop_search(props, "collection_name", bpy.data, "collections", text="Choose Collection")
        layout.prop(props, "data_property")
        layout.prop(props, "bounding_box_object")
        layout.prop(props, "grid_size")
        layout.prop(props, "normalize_colormap")
        if props.normalize_colormap:
            layout.prop(props, "iqr_scaling_factor")
        layout.prop(props, "rbf_function")
        layout.prop(props, "epsilon_value")
        
        layout.operator("mesh.collection_mesh_generate_interpolated_block", text="Generate Block Model", icon='PLAY')

class IMPORT_OT_generate_interpolated_block(bpy.types.Operator):
    bl_idname = "mesh.collection_mesh_generate_interpolated_block"
    bl_label = "Generate Interpolated Block Model"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            props = context.scene.interpolated_volume_tool
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

            if props.epsilon_value == 1.0:  # Default value, calculates average distance, dont think it works 
                props.epsilon_value = calculate_default_epsilon(filtered_x, filtered_y, filtered_z)

            rbf = Rbf(filtered_x, filtered_y, filtered_z, filtered_d, function=props.rbf_function, epsilon=props.epsilon_value, smooth=0.1)
            grid_x, grid_y, grid_z = np.mgrid[bbox_min.x:bbox_max.x:props.grid_size*1j,
                                              bbox_min.y:bbox_max.y:props.grid_size*1j,
                                              bbox_min.z:bbox_max.z:props.grid_size*1j]
            scalar_field = rbf(grid_x, grid_y, grid_z)

            if props.normalize_colormap:
                q75, q25 = np.percentile(scalar_field, [75, 25])
                iqr = q75 - q25
                lower_bound = q25 - (props.iqr_scaling_factor * iqr)
                upper_bound = q75 + (props.iqr_scaling_factor * iqr)
                filtered_values = [v for v in scalar_field.flatten() if lower_bound <= v <= upper_bound]
                min_val = min(filtered_values) if filtered_values else q25
                max_val = max(filtered_values) if filtered_values else q75
            else:
                min_val, max_val = np.min(scalar_field), np.max(scalar_field)

            self.report({'INFO'}, "RBF interpolation completed successfully.")
            
            spacing_x = (bbox_max.x - bbox_min.x) / (props.grid_size - 1)
            spacing_y = (bbox_max.y - bbox_min.y) / (props.grid_size - 1)
            spacing_z = (bbox_max.z - bbox_min.z) / (props.grid_size - 1)

            cube_size_x = spacing_x * 0.9
            cube_size_y = spacing_y * 0.9
            cube_size_z = spacing_z * 0.9

            cube_data = []
            for i in range(scalar_field.shape[0]):
                for j in range(scalar_field.shape[1]):
                    for k in range(scalar_field.shape[2]):
                        xv = grid_x[i, j, k]
                        yv = grid_y[i, j, k]
                        zv = grid_z[i, j, k]
                        val = scalar_field[i, j, k]
                        cube_location = (xv, yv, zv)
                        cube_data.append((cube_location, (cube_size_x, cube_size_y, cube_size_z), val))

            cube_data_sorted = sorted(cube_data, key=lambda x: x[2], reverse=True)

            master_collection_name = f"{props.data_property}_Block Model"
            master_collection = bpy.data.collections.new(master_collection_name)
            bpy.context.scene.collection.children.link(master_collection)

            cubes_per_group = len(cube_data_sorted) // 10
            collections = [bpy.data.collections.new(f"Interpolated_Collection_{i}") for i in range(10)]
            for i, collection in enumerate(collections):
                master_collection.children.link(collection)

            template_cube = create_template_cube(1)

            for index, data in enumerate(cube_data_sorted):
                group_index = index // cubes_per_group
                group_index = min(group_index, 9)
                cube_location, cube_size, val = data

                
                cube = duplicate_cube(template_cube, cube_location, cube_size, val)
                apply_color_to_cube(cube, val, min_val, max_val)

                for collection in cube.users_collection:
                    collection.objects.unlink(cube)

                collections[group_index].objects.link(cube)

            
            bpy.data.objects.remove(template_cube)  

            self.report({'INFO'}, "Block model generated and added to the scene.")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Unexpected error: {e}")
            return {'CANCELLED'}

def create_template_cube(size, name="TemplateCube"):
    bpy.ops.mesh.primitive_cube_add(size=size)
    cube = bpy.context.object
    cube.name = name
    cube.hide_render = True
    return cube

def duplicate_cube(template_cube, location, size_factors, d_value):
    new_cube = template_cube.copy()
    new_cube.data = template_cube.data.copy()
    new_cube.location = location
    new_cube.scale = size_factors
    
    new_cube.name = f"{d_value:.2f}"
    new_cube.hide_render = False
    bpy.context.collection.objects.link(new_cube)

    # Add custom properties for x, y, z, and d
    new_cube["X"] = location[0]
    new_cube["Y"] = location[1]
    new_cube["Z"] = location[2]
    new_cube["Interpolated Value"] = d_value

    return new_cube



def apply_color_to_cube(cube, value, min_val, max_val):
    color_map = plt.get_cmap('Spectral_r')
    normalized_value = (value - min_val) / (max_val - min_val)
    color = color_map(normalized_value)[:4]
    color = (*color[:3], 0.5)
    
    mat = bpy.data.materials.new(name="CubeMaterial")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = color
    bsdf.inputs['Alpha'].default_value = 0.5
    
    mat.blend_method = 'BLEND'
    cube.data.materials.append(mat)

classes = [
    InterpolatedVolumeProperties,
    IMPORT_OT_generate_interpolated_block,
    IMPORT_PT_panel_interpolated_block
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Scene.interpolated_volume_tool = bpy.props.PointerProperty(type=InterpolatedVolumeProperties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    del bpy.types.Scene.interpolated_volume_tool

if __name__ == "__main__":
    register()
