import bpy
from bpy.props import EnumProperty, StringProperty
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator, Panel
import csv
import math
from mathutils import Vector
from ..preferences import get_preferences  


# Global variables to hold CSV data and columns
csv_data = []
csv_columns = []

def read_csv(filepath):
    global csv_columns, csv_data
    with open(filepath, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        csv_columns = reader.fieldnames
        csv_data = [row for row in reader]

def get_csv_column_names(self, context):
    return [(col, col, "") for col in csv_columns]

class DrillHoleRenderPanel(bpy.types.Panel): # UI Panel
    bl_label = "Import Drill Holes (.csv)"
    bl_idname = "IMPORT_PT_panel_DDH"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'GeoModeller'  
    bl_parent_id = "GEOMOD_PT_drilling_category"  
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.operator("import.load_csv", text="Load CSV")

        if hasattr(context.scene, 'csv_file_path') and context.scene.csv_file_path:
            layout.label(text="File loaded: " + context.scene.csv_file_path)
            if csv_columns:
                layout.label(text="Select Columns:")
                for col_name in ['hole_id', 'x', 'y', 'z']:
                    prop_name = f"csv_column_{col_name}"
                    layout.prop(context.scene, prop_name, text=col_name.capitalize())
            layout.operator("import.drill_holes", text="Import Drill Holes", icon='PLAY')


class LoadCSVOperator(bpy.types.Operator, ImportHelper): # Load CSV file
    bl_idname = "import.load_csv"
    bl_label = "Load CSV"
    filter_glob: bpy.props.StringProperty(default="*.csv", options={'HIDDEN'}, maxlen=255)

    def execute(self, context):
        context.scene.csv_file_path = self.filepath
        update_csv_columns(self.filepath)  # Update column selection 
        return {'FINISHED'}


def create_curve(start, end, curve_name, row_data):
    curve_data = bpy.data.curves.new(curve_name, type='CURVE')
    curve_data.dimensions = '3D'
    curve_data.bevel_depth = 1.5  # Fixed radius to start
    curve_data.use_fill_caps = True

    spline = curve_data.splines.new(type='POLY')
    spline.points.add(1)
    spline.points[0].co = (start[0], start[1], start[2], 1)
    spline.points[1].co = (end[0], end[1], end[2], 1)

    curve_obj = bpy.data.objects.new(curve_name, curve_data)
    bpy.context.collection.objects.link(curve_obj)
    
    # Add custom properties polarity az dip (for modeling)
    add_custom_properties(curve_obj)
    
    # Add custom properties based on CSV column headers and row data
    for key, value in row_data.items():
        curve_obj[key] = value
    
    return curve_obj

def read_csv_data(file_path, hole_id_col, x_col, y_col, z_col):
    data = []
    lowest_z_per_hole = {}
    with open(file_path, 'r') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            try:
                hole_id = row[hole_id_col]
                x, y, z = float(row[x_col]), float(row[y_col]), float(row[z_col])
                
                # Check if x, y, or z is NaN and skip the row 
                if math.isnan(x) or math.isnan(y) or math.isnan(z):
                    continue  # Skip to the next row

                curve_name = f"DrillHole_{hole_id}"
                row_data = {key: row[key] for key in row}  # Creating a full copy of the row data
                row_data.update({
                    x_col: x,  # Overwrite x, y, z using dynamic column names
                    y_col: y,
                    z_col: z,
                    'curve_name': curve_name
                })

                if hole_id not in lowest_z_per_hole or z < lowest_z_per_hole[hole_id][z_col]:
                    lowest_z_per_hole[hole_id] = row_data

                data.append(row_data)
            except ValueError:
                continue

    # Sorting the data if 'use_z_descending' is enabled
    preferences = get_preferences()
    if preferences.use_z_descending:
        # group data by hole_id
        from itertools import groupby
        data.sort(key=lambda row: row[hole_id_col])  
        grouped_data = []
        
        # for each hole_id group, sort by Z in descending order
        for hole_id, group in groupby(data, key=lambda row: row[hole_id_col]):
            sorted_group = sorted(group, key=lambda row: row[z_col], reverse=True)  
            grouped_data.extend(sorted_group)  # Append sorted group to final list
        
        data = grouped_data  # Update data with sorted groups

    return data, lowest_z_per_hole


def add_custom_properties(obj):
    # Check and add custom properties 'azimuth, 'polaorty', 'dip 'if they don't already exist
    if "polarity" not in obj:
        obj["polarity"] = 1
        if "_RNA_UI" not in obj:
            obj["_RNA_UI"] = {}
        obj["_RNA_UI"]["polarity"] = {"max": 1, "description": "Polarity (0-1)", "override_library_create": True}

    if "azimuth" not in obj:
        obj["azimuth"] = 0
        obj["_RNA_UI"]["azimuth"] = {"max": 360, "description": "Azimuth (0-360)", "override_library_create": True}

    if "dip" not in obj:
        obj["dip"] = 0
        obj["_RNA_UI"]["dip"] = {"max": 90, "description": "Dip (0-90)", "override_library_create": True}

def create_marker_cube(location, name, size=0.1): # for drill hole Ids, bottom of each drill trace
    bpy.ops.mesh.primitive_cube_add(size=size, location=location)
    cube = bpy.context.object
    cube.name = name
    cube.show_name = True

    return cube

def calculate_offset(data, x_col, y_col, z_col):
    # Access the add-on preferences
    preferences = get_preferences()
    
    if preferences.use_scene_crs:  # Check if "Use Scene CRS" is enabled
        # offset calculation, i dont like this messy math
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


def create_collections(base_name="Drill Hole Collection"):
    # Create or get the collection for drill holes
    if base_name not in bpy.data.collections:
        main_collection = bpy.data.collections.new(base_name)
        bpy.context.scene.collection.children.link(main_collection)
    else:
        main_collection = bpy.data.collections[base_name]

    # Store references to all hole_id specific sub-collections
    hole_id_collections = {}
    
    # Create or get the collection for marker cubes (hole_ids)
    marker_collection_name = "Hole ID Collection"
    if marker_collection_name not in bpy.data.collections:
        marker_collection = bpy.data.collections.new(marker_collection_name)
        bpy.context.scene.collection.children.link(marker_collection)
    else:
        marker_collection = bpy.data.collections[marker_collection_name]

    # Create or get the collection for drill hole traces
    trace_collection_name = "Drill Hole Traces"
    if trace_collection_name not in bpy.data.collections:
        trace_collection = bpy.data.collections.new(trace_collection_name)
        bpy.context.scene.collection.children.link(trace_collection)
    else:
        trace_collection = bpy.data.collections[trace_collection_name]

    return main_collection, marker_collection, hole_id_collections, trace_collection


def link_to_appropriate_collection(curve_obj, hole_id, main_collection, hole_id_collections):
    # If there's no sub-collection for this hole_id, create it and link to the main collection
    if hole_id not in hole_id_collections:
        hole_id_collection_name = f"{hole_id}"
        hole_id_collection = bpy.data.collections.new(hole_id_collection_name)
        main_collection.children.link(hole_id_collection)  # Link the sub-collection to the main collection
        hole_id_collections[hole_id] = hole_id_collection
    
    # Link the curve object to its respective hole_id collection
    hole_id_collections[hole_id].objects.link(curve_obj)

def merge_curves(curve_objs, merged_curve_name): # creates drill hole trace per hole_id
    merged_curve_data = bpy.data.curves.new(merged_curve_name, type='CURVE')
    merged_curve_data.dimensions = '3D'
    merged_curve_data.bevel_depth = 0  # No bevel for the drill trace
    merged_curve_data.use_fill_caps = False

    for curve_obj in curve_objs:
        for spline in curve_obj.data.splines:
            new_spline = merged_curve_data.splines.new(type='POLY')
            new_spline.points.add(len(spline.points) - 1)
            for i, point in enumerate(spline.points):
                new_spline.points[i].co = point.co

    merged_curve_obj = bpy.data.objects.new(merged_curve_name, merged_curve_data)
    merged_curve_obj.display_type = 'WIRE'  # Display as wire

    # Unlink from all collections initially
    for collection in merged_curve_obj.users_collection:
        collection.objects.unlink(merged_curve_obj)

    bpy.context.collection.objects.link(merged_curve_obj)

    return merged_curve_obj

def execute_import(context, data, main_collection, hole_id_collections, trace_collection, hole_id_col, x_col, y_col, z_col):
    # Set scene units to metric and scale
    bpy.context.scene.unit_settings.system = 'METRIC' # ensure blender units are set to meters
    bpy.context.scene.unit_settings.scale_length = 1  # 1 Blender unit = 1 meter

    offset = calculate_offset(data, x_col, y_col, z_col)

    previous_row = None  # Initialize previous_row to handle the first point
    hole_id_to_curves = {}  # Dictionary to store curves by hole_id
    for row_data in data:
        if previous_row is not None and previous_row[hole_id_col] == row_data[hole_id_col]:
            # Calculate start and end points using offset
            start = Vector((previous_row[x_col] + offset[0], previous_row[y_col] + offset[1], previous_row[z_col] + offset[2]))
            end = Vector((row_data[x_col] + offset[0], row_data[y_col] + offset[1], row_data[z_col] + offset[2]))
            curve_name = row_data['curve_name']  
            
            # Create curve and link to appropriate collection
            curve_obj = create_curve(start, end, curve_name, row_data)
            bpy.context.collection.objects.unlink(curve_obj)  # Unlink from the default collection
            link_to_appropriate_collection(curve_obj, row_data[hole_id_col], main_collection, hole_id_collections)

            # Store the curve object in the dictionary by hole_id
            if row_data[hole_id_col] not in hole_id_to_curves:
                hole_id_to_curves[row_data[hole_id_col]] = []
            hole_id_to_curves[row_data[hole_id_col]].append(curve_obj)
        
        # Update previous_row to the current row for the next iteration
        previous_row = row_data


    # Merge curves for each hole_id and link to the trace collection
    for hole_id, curve_objs in hole_id_to_curves.items():
        merged_curve_name = f"{hole_id} trace"
        merged_curve_obj = merge_curves(curve_objs, merged_curve_name)
        
        # Unlink from the main collection and link to the trace collection
        bpy.context.collection.objects.unlink(merged_curve_obj)  
        trace_collection.objects.link(merged_curve_obj)  # Link to the trace collection
        
def update_csv_columns(filepath): # update with CSV upload
    try:
        with open(filepath, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            global csv_columns
            csv_columns = reader.fieldnames
            items = [(col, col, "") for col in csv_columns]
            for col_name in ['hole_id', 'x', 'y', 'z']:
                prop_name = f"csv_column_{col_name}"
                setattr(bpy.types.Scene, prop_name, bpy.props.EnumProperty(items=items, name=col_name.capitalize()))
    except Exception as e:
        print("Failed to read CSV columns:", e)

class IMPORT_OT_drill_holes(bpy.types.Operator):
    bl_idname = "import.drill_holes"
    bl_label = "Upload Drill Holes"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Retrieve the filepath and column identifiers from the scene properties
        filepath = context.scene.csv_file_path
        hole_id_col = context.scene.csv_column_hole_id
        x_col = context.scene.csv_column_x
        y_col = context.scene.csv_column_y
        z_col = context.scene.csv_column_z

        # Ensure all necessary data is present 
        if not filepath:
            self.report({'ERROR'}, "No file selected.")
            return {'CANCELLED'}
        if not all([hole_id_col, x_col, y_col, z_col]):
            self.report({'ERROR'}, "One or more column identifiers are missing.")
            return {'CANCELLED'}

        # Call the data reading function with all required parameters
        try:
            data, lowest_z_per_hole = read_csv_data(filepath, hole_id_col, x_col, y_col, z_col)
            main_collection, marker_collection, hole_id_collections, trace_collection = create_collections()
            execute_import(context, data, main_collection, hole_id_collections, trace_collection, hole_id_col, x_col, y_col, z_col)

            # Create marker cubes at the lowest points (drill hole IDs)
            marker_offset = 0.5  
            offset = calculate_offset(data, x_col, y_col, z_col)
            for hole_id, lowest_data in lowest_z_per_hole.items():
                marker_location = (lowest_data[x_col] + offset[0], lowest_data[y_col] + offset[1], lowest_data[z_col] + offset[2] - marker_offset)
                marker_cube = create_marker_cube(marker_location, hole_id)
                bpy.context.collection.objects.unlink(marker_cube)  # Unlink from current collection
                marker_collection.objects.link(marker_cube)
                
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

def register():
    bpy.utils.register_class(DrillHoleRenderPanel)
    bpy.utils.register_class(LoadCSVOperator)
    bpy.utils.register_class(IMPORT_OT_drill_holes)
    bpy.types.Scene.csv_file_path = bpy.props.StringProperty(name="CSV File Path")
    bpy.types.Scene.csv_column_hole_id = bpy.props.EnumProperty(items=get_csv_column_names, name="Hole ID")
    bpy.types.Scene.csv_column_x = bpy.props.EnumProperty(items=get_csv_column_names, name="X")
    bpy.types.Scene.csv_column_y = bpy.props.EnumProperty(items=get_csv_column_names, name="Y")
    bpy.types.Scene.csv_column_z = bpy.props.EnumProperty(items=get_csv_column_names, name="Z")
    

def unregister():
    bpy.utils.unregister_class(DrillHoleRenderPanel)
    bpy.utils.unregister_class(LoadCSVOperator)
    bpy.utils.unregister_class(IMPORT_OT_drill_holes)
    del bpy.types.Scene.csv_file_path
    del bpy.types.Scene.csv_column_hole_id
    del bpy.types.Scene.csv_column_x
    del bpy.types.Scene.csv_column_y
    del bpy.types.Scene.csv_column_z
    

if __name__ == "__main__":
    register()
