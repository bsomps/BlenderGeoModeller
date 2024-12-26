import bpy
import csv
from mathutils import Vector
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator, Panel
from bpy.props import EnumProperty, StringProperty
from ..preferences import get_preferences

# Global variables to hold CSV data
csv_data_points = []
csv_columns_points = []

def read_csv_points(filepath):
    global csv_columns_points, csv_data_points
    with open(filepath, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        csv_columns_points = reader.fieldnames
        csv_data_points = [row for row in reader]

def get_csv_column_names_points(self, context):
    return [(col, col, "") for col in csv_columns_points]

class PointsRenderPanel(bpy.types.Panel): # UI Panel
    bl_label = "Import Point Data (.csv)"
    bl_idname = "IMPORT_PT_panel_points"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'GeoModeller'
    bl_parent_id = "GEOMOD_PT_points_category"
    bl_options = {'DEFAULT_CLOSED'}  
    
    def draw(self, context):
        layout = self.layout
        layout.operator("import_points.load_csv", text="Load CSV")

        if hasattr(context.scene, 'csv_file_path_points') and context.scene.csv_file_path_points:
            layout.label(text="File loaded: " + context.scene.csv_file_path_points)
            if csv_columns_points:
                layout.label(text="Select Columns:")
                for col_name in ['x', 'y', 'z']:
                    prop_name = f"csv_column_{col_name}_points"
                    layout.prop(context.scene, prop_name, text=col_name.capitalize())
            layout.operator("import_points.create_points", text="Import Points", icon='PLAY')

class LoadCSVOperatorPoints(bpy.types.Operator, ImportHelper): # load CSV
    bl_idname = "import_points.load_csv"
    bl_label = "Load CSV"
    filter_glob: bpy.props.StringProperty(default="*.csv", options={'HIDDEN'}, maxlen=255)

    def execute(self, context):
        context.scene.csv_file_path_points = self.filepath
        update_csv_columns_points(self.filepath)  # Update column selection 
        return {'FINISHED'}

def get_viewport_clip_end(): # Retrieve the 'Clip End' value from the 3D Viewport's View settings
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    return space.clip_end
    return 10000.0  # Default fallback if not found


def create_template_sphere(name="TemplateSphere"):
    # Access the viewport's clip end value
    clip_end = get_viewport_clip_end()
    
    # Calculate radius based on clip end
    radius = clip_end * 0.0012

    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius)
    sphere = bpy.context.object
    sphere.name = name
    sphere.hide_render = True
    return sphere


def duplicate_sphere(template_sphere, location, name="Point"):
    new_sphere = template_sphere.copy()
    new_sphere.data = template_sphere.data.copy()
    new_sphere.location = location
    new_sphere.name = name
    new_sphere.hide_render = False
    bpy.context.collection.objects.link(new_sphere)
    return new_sphere

def create_sphere(location, name, row_data, template_sphere, collection):
    sphere = duplicate_sphere(template_sphere, location, name)

    # Add custom properties based on CSV column headers and row data
    for key, value in row_data.items():
        sphere[key] = value
    
    collection.objects.link(sphere)
    bpy.context.collection.objects.unlink(sphere)
    return sphere

def read_csv_data_points(file_path, x_col, y_col, z_col):
    data = []
    with open(file_path, 'r') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            x, y, z = float(row[x_col]), float(row[y_col]), float(row[z_col])
            row_data = {key: row[key] for key in row}
            row_data.update({
                x_col: x,
                y_col: y,
                z_col: z
            })
            data.append(row_data)
    return data

def calculate_offset_points(data, x_col, y_col, z_col):
    # Access the add-on preferences
    preferences = get_preferences()
    
    if preferences.use_scene_crs:  # Check if "Use Scene CRS" is enabled
        
        drill_hole_ref_x = max(data, key=lambda d: d[z_col])[x_col]
        drill_hole_ref_y = max(data, key=lambda d: d[z_col])[y_col]
        drill_hole_ref_z = max(data, key=lambda d: d[z_col])[z_col]

        scene = bpy.context.scene

        dem_ref_x = drill_hole_ref_x - scene['crs x'] if 'crs x' in scene else 0
        dem_ref_y = drill_hole_ref_y - scene['crs y'] if 'crs y' in scene else 0

        offset_x = dem_ref_x - drill_hole_ref_x
        offset_y = dem_ref_y - drill_hole_ref_y
        offset_z = 0
    else:
        # If the checkbox is unchecked, return (0, 0, 0)
        offset_x = 0
        offset_y = 0
        offset_z = 0

    return (offset_x, offset_y, offset_z)

def update_csv_columns_points(filepath):
    try:
        with open(filepath, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            global csv_columns_points
            csv_columns_points = reader.fieldnames
            items = [(col, col, "") for col in csv_columns_points]
            for col_name in ['x', 'y', 'z']:
                prop_name = f"csv_column_{col_name}_points"
                setattr(bpy.types.Scene, prop_name, bpy.props.EnumProperty(items=items, name=col_name.capitalize()))
    except Exception as e:
        print("Failed to read CSV columns:", e)

class IMPORT_OT_create_points(bpy.types.Operator):
    bl_idname = "import_points.create_points"
    bl_label = "Create Points"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # get filepath and column identifiers from the scene properties
        filepath = context.scene.csv_file_path_points
        x_col = context.scene.csv_column_x_points
        y_col = context.scene.csv_column_y_points
        z_col = context.scene.csv_column_z_points

        
        if not filepath:
            self.report({'ERROR'}, "No file selected.")
            return {'CANCELLED'}
        if not all([x_col, y_col, z_col]):
            self.report({'ERROR'}, "One or more column identifiers are missing.")
            return {'CANCELLED'}

        
        try:
            data = read_csv_data_points(filepath, x_col, y_col, z_col)
            offset = calculate_offset_points(data, x_col, y_col, z_col)
            
            # Create a template sphere
            template_sphere = create_template_sphere()
            
            # Create a new collection for the points
            points_collection_name = "Points Collection"
            points_collection = bpy.data.collections.new(points_collection_name)
            bpy.context.scene.collection.children.link(points_collection)

            for row_data in data:
                location = (row_data[x_col] + offset[0], row_data[y_col] + offset[1], row_data[z_col] + offset[2])
                name = f"Point_{row_data[x_col]}_{row_data[y_col]}_{row_data[z_col]}"
                create_sphere(location, name, row_data, template_sphere, points_collection)

            bpy.data.objects.remove(template_sphere)  # Remove the template sphere after creating all points

            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

def register():
    bpy.utils.register_class(PointsRenderPanel)
    bpy.utils.register_class(LoadCSVOperatorPoints)
    bpy.utils.register_class(IMPORT_OT_create_points)
    bpy.types.Scene.csv_file_path_points = bpy.props.StringProperty(name="CSV File Path")
    bpy.types.Scene.csv_column_x_points = bpy.props.EnumProperty(items=get_csv_column_names_points, name="X")
    bpy.types.Scene.csv_column_y_points = bpy.props.EnumProperty(items=get_csv_column_names_points, name="Y")
    bpy.types.Scene.csv_column_z_points = bpy.props.EnumProperty(items=get_csv_column_names_points, name="Z")
    

def unregister():
    bpy.utils.unregister_class(PointsRenderPanel)
    bpy.utils.unregister_class(LoadCSVOperatorPoints)
    bpy.utils.unregister_class(IMPORT_OT_create_points)
    del bpy.types.Scene.csv_file_path_points
    del bpy.types.Scene.csv_column_x_points
    del bpy.types.Scene.csv_column_y_points
    del bpy.types.Scene.csv_column_z_points
    

if __name__ == "__main__":
    register()
