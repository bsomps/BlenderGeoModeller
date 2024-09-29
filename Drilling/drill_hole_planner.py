import bpy
from bpy.props import EnumProperty, StringProperty
from bpy_extras.io_utils import ImportHelper
from bpy_extras.io_utils import ExportHelper
from bpy.types import Operator, Panel
import csv
import numpy as np
import math
from math import sin, cos, radians
from ..preferences import get_preferences


# loaded CSV data
csv_data = []
csv_columns = []


# read CSV and update column names
def read_csv(filepath):
    global csv_columns, csv_data
    with open(filepath, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        csv_columns = reader.fieldnames
        csv_data = [row for row in reader]
        

def get_csv_column_names(self, context):
    return [(col, col, "") for col in csv_columns]
    
def get_collections(self, context):
    collections = bpy.data.collections
    collection_items = [(col.name, col.name, "") for col in collections if any(obj.type == 'CURVE' for obj in col.objects)]
    return collection_items

    
    
class DrillHolePlannerPanel(bpy.types.Panel):
    bl_label = "Drill Hole Planner"
    bl_idname = "OBJECT_PT_drillholeplanner"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'GeoModeller'  
    bl_parent_id = "GEOMOD_PT_drilling_category"  
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        # Button to load CSV file
        layout.operator("import_test.csv_load", text="Load Planned Drill Holes (CSV)")

        
        if csv_columns:
            layout.label(text="Select Columns:")
            layout.prop(context.scene, "csv_column_hole_d", text="Hole ID")
            layout.prop(context.scene, "csv_column_x", text="X")
            layout.prop(context.scene, "csv_column_y", text="Y")
            layout.prop(context.scene, "csv_column_z", text="Z")
            layout.prop(context.scene, "csv_column_total_depth", text="Total Depth (meters)")
            layout.prop(context.scene, "csv_column_azimuth", text="Azimuth")
            layout.prop(context.scene, "csv_column_dip", text="Dip")

            # Button to calculate drill hole traces
            layout.operator("object.drillholeplanner_operator", text="Render Planned Holes", icon='PLAY')
            
        # Export section 
        if bpy.data.collections:  
            layout.label(text="Export Drill Holes:")
            layout.prop(context.scene, "selected_collection", text="Collection")
            layout.operator("export.drillholes", text="Export Planned Drill Holes")
            
            

# loading CSV, updates csv_data and csv_columns
class LoadCSVOperator(Operator, ImportHelper):
    """Load CSV File"""
    bl_idname = "import_test.csv_load"
    bl_label = "Load Planned Drill Holes (CSV)"
    filename_ext = ".csv"

    filter_glob: StringProperty(
        default="*.csv",
        options={'HIDDEN'},
        maxlen=255,
    )

    def execute(self, context):
        read_csv(self.filepath)
        print(f"Loaded {self.filepath}")
        return {'FINISHED'}
        
def calculate_offset(x, y, z, scene): # offset for scene CRS 
    
    preferences = get_preferences()

    if preferences.use_scene_crs:  # Check if "Use Scene CRS" is enabled
        # Use the coordinates of the highest value as the reference point
        ref_x = x
        ref_y = y
        ref_z = z
        print (ref_x, ref_y, ref_z)

        # Access the custom properties 'crs x' and 'crs y' from the scene properties
        dem_ref_x = ref_x - scene.get('crs x', 0)
        dem_ref_y = ref_y - scene.get('crs y', 0)
        print (dem_ref_x, dem_ref_y)

        # Calculate the offset
        offset_x = dem_ref_x - ref_x
        offset_y = dem_ref_y - ref_y
        offset_z = 0
        print (offset_x, offset_y, offset_z)
        
    else:
        # If the checkbox is unchecked (no scene crs), return (0, 0, 0)
        offset_x = 0
        offset_y = 0
        offset_z = 0

    return (offset_x, offset_y, offset_z)

# Calculate final coordinates based on selected column values
def calculate_final_coordinates(x, y, z, total_depth, azimuth, dip):
    X = x + (total_depth) * sin(radians(azimuth)) * cos(radians(dip))
    Y = y + (total_depth) * cos(radians(azimuth)) * cos(radians(dip))
    Z = z + ((total_depth) * sin(radians(dip)))
    
    return X, Y, Z
    
def calculate_azimuth_dip(start_vec, end_vec):
    direction = end_vec - start_vec
    direction.normalize()
    
    # Azimuth calculation
    azimuth_rad = math.atan2(direction.x, direction.y)
    azimuth_deg = math.degrees(azimuth_rad)
    
    # keep azimuth is in the range [0, 360]
    if azimuth_deg < 0:
        azimuth_deg += 360

    # Dip calculation
    dip_rad = math.asin(direction.z)
    dip_deg = math.degrees(dip_rad)

    return azimuth_deg, dip_deg


def calculate_length(start_vec, end_vec):
    return (end_vec - start_vec).length

# create drill holes based on column selections
class DrillHolePlannerOperator(bpy.types.Operator):
    bl_idname = "object.drillholeplanner_operator"
    bl_label = "Calculate Drill Hole Traces"

    def execute(self, context):
        scene = context.scene

        unique_hole_ids = set(row[scene.csv_column_hole_d] for row in csv_data)
        for hole_id in unique_hole_ids:
        
            # Fetch row data
            row = next(row for row in csv_data if row[scene.csv_column_hole_d] == hole_id)
            x = float(row[scene.csv_column_x])
            y = float(row[scene.csv_column_y])
            z = float(row[scene.csv_column_z])
            total_depth = float(row[scene.csv_column_total_depth])
            azimuth = float(row[scene.csv_column_azimuth])
            dip = float(row[scene.csv_column_dip])
            
            # Calculate final coordinates
            final_x, final_y, final_z = calculate_final_coordinates(x, y, z, total_depth, azimuth, dip)

            # offset
            offset = calculate_offset(x, y, z, bpy.context.scene)

            # Adjust points with offset and make the final point as origin
            adjusted_x = x + offset[0] - (final_x + offset[0])
            adjusted_y = y + offset[1] - (final_y + offset[1])
            adjusted_z = z + offset[2] - (final_z + offset[2])

            # Create curve between initial and final points
            curve_data = bpy.data.curves.new(name=f"{hole_id}", type='CURVE')
            curve_data.dimensions = '3D'

            polyline = curve_data.splines.new('POLY')
            polyline.points.add(1)  
            polyline.points[0].co = (adjusted_x, adjusted_y, adjusted_z, 1)
            polyline.points[1].co = (0, 0, 0, 1)  # Final point as origin after adjustment for drill hole naming

            curve_object = bpy.data.objects.new(f"{hole_id}", curve_data)
            scene.collection.objects.link(curve_object)

            # Move curve object to place the origin at the calculated final point plus offset
            curve_object.location = (final_x + offset[0], final_y + offset[1], final_z + offset[2])

            #### FIX appearance settings
            curve_object.data.bevel_depth = 2  # Adjust maybe
            curve_object.data.use_fill_caps = True
            curve_object.show_name = True
            if not bpy.data.materials.get("BlackMaterial"):
                bpy.data.materials.new(name="BlackMaterial")
            curve_object.data.materials.append(bpy.data.materials["BlackMaterial"])

        return {'FINISHED'}
        
def find_highest_and_lowest_points(curve):
    # Striath line curve only
    points_local = [point.co for point in curve.data.splines[0].points]
    
    # Convert points to world coordinates
    points_world = [curve.matrix_world @ point_local for point_local in points_local]
    
    # Sort the points by their z value in descending order
    points_sorted_by_z = sorted(points_world, key=lambda p: p.z, reverse=True)
    
    
    highest_point_world = points_sorted_by_z[0]
    
    
    lowest_point_world = points_sorted_by_z[-1]

    return highest_point_world, lowest_point_world


# export drill holes
class EXPORT_DrillHoles(bpy.types.Operator, ExportHelper):
    bl_idname = "export.drillholes"
    bl_label = "Export Drill Holes"
    filename_ext = ".csv"

    # ExportHelper mixin class
    filter_glob: StringProperty(
        default='*.csv',
        options={'HIDDEN'},
    )

    def execute(self, context):
        selected_collection_name = context.scene.selected_collection
        selected_collection = bpy.data.collections.get(selected_collection_name)
        if not selected_collection:
            self.report({'ERROR'}, "Collection not found")
            return {'CANCELLED'}

        # check "Use Scene CRS" from preferences
        preferences = get_preferences()
        use_scene_crs = preferences.use_scene_crs

        
        filepath = self.filepath

        with open(filepath, 'w', newline='') as csvfile:
            fieldnames = ['hole_id', 'x', 'y', 'elevation', 'azimuth', 'dip', 'total depth']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for obj in selected_collection.objects:
                if obj.type == 'CURVE':
                
                    # determine start and end points
                    highest_point_world, lowest_point_world = find_highest_and_lowest_points(obj)

                    if use_scene_crs:
                        # Get 'crs x' and 'crs y' from scene properties
                        crs_x = bpy.context.scene.get('crs x', 0)
                        crs_y = bpy.context.scene.get('crs y', 0)

                        # Adjust x, y with 'crs x' and 'crs y' for the highest point (start point)
                        x = highest_point_world.x + crs_x
                        y = highest_point_world.y + crs_y
                    else:
                        # If "Use Scene CRS" is unchecked, use the world coordinates directly
                        x = highest_point_world.x
                        y = highest_point_world.y
                    
                    # Elevation is the z value of the highest point
                    z = highest_point_world.z

                    # Calculate azimuth, dip, and total depth
                    azimuth, dip = calculate_azimuth_dip(highest_point_world, lowest_point_world)
                    total_depth = calculate_length(highest_point_world, lowest_point_world)

                    writer.writerow({
                        'hole_id': obj.name,
                        'x': x,
                        'y': y,
                        'elevation': z,
                        'azimuth': round(azimuth),  # Round azimuth to nearest whole number
                        'dip': round(dip),  # Round dip to nearest whole number
                        'total depth': total_depth
                    })

        self.report({'INFO'}, f"Exported drill holes to {filepath}")
        return {'FINISHED'}

        
# Classes to register
classes = [
    DrillHolePlannerPanel,
    LoadCSVOperator,
    DrillHolePlannerOperator,
    EXPORT_DrillHoles
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.csv_column_hole_d = bpy.props.EnumProperty(items=get_csv_column_names, name="Hole ID")
    bpy.types.Scene.csv_column_x = bpy.props.EnumProperty(items=get_csv_column_names, name="X")
    bpy.types.Scene.csv_column_y = bpy.props.EnumProperty(items=get_csv_column_names, name="Y")
    bpy.types.Scene.csv_column_z = bpy.props.EnumProperty(items=get_csv_column_names, name="Z")
    bpy.types.Scene.csv_column_total_depth = bpy.props.EnumProperty(items=get_csv_column_names, name="Total Depth")
    bpy.types.Scene.csv_column_azimuth = bpy.props.EnumProperty(items=get_csv_column_names, name="Azimuth")
    bpy.types.Scene.csv_column_dip = bpy.props.EnumProperty(items=get_csv_column_names, name="Dip")
    bpy.types.Scene.selected_collection = bpy.props.EnumProperty(items=get_collections, name="Collection")

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    props = [
        'csv_column_hole_d',
        'csv_column_x',
        'csv_column_y',
        'csv_column_z',
        'csv_column_total_depth',
        'csv_column_azimuth',
        'csv_column_dip',
        'selected_collection'
    ]
    
    for prop in props:
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)

if __name__ == "__main__":
    register()

