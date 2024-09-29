import bpy
from mathutils import Vector
import bmesh
import pandas as pd
import os
import numpy as np
import gempy as gp
import string
import tempfile
from itertools import count
from string import ascii_uppercase
from gempy_engine.core.data.stack_relation_type import StackRelationType
print("Import successful:", StackRelationType.FAULT)
import re  
from bpy.props import CollectionProperty, BoolProperty, EnumProperty



# This code attempts to emulate the workflow of the gempy module through the UI panel. 
# Note that several parameters that are availble through the gempy module are left out
# the code does not attempt to create the lith blocks, they can be brought in as point clouds,
# but I have not figured out a clean way to display these blocks as a mesh in blender

# 1. Create model extents by drawing a cube around the area you want to model (this sets xmin, xmax, ymin, ymax, zmin, zmax). Name you model and set the refinment (6 is recommended)
# 2. Choose your 'formations' and 'orientations' data you want to complile into a CSV. CSVs are created from objects within collections. This can be points (mesh) of drill hole intervals (curves) 
#    formation names will populate based on its name in the outliner, and polarity, azimuth, and dip will be populated from the custom properties
# 2. Strat series and fault series can then be added and organized based on user input. The 'order' dictates the geologic age, 0 is youngest.
#    Each series relation type can be set to "ERODE", "ONLAP" or "BASEMENT" and the faults series are automatically set to "FAULT". The fault relations matrix is created dynamically based on 'order' inputs
# 3. The result is a collection of all the surfaces (mesh objects) generated through the gempy engine. Once in blender
#    these mesh objects can be cleaned up, edited, used to create lith blocks ect...
#  Check you console window to view the structral frame after generating the model


def update_cube_extents(self, context):
    cube = self.cube_object
    if cube:
        # Get the bounding box coordinates
        bbox_corners = [cube.matrix_world @ Vector(corner) for corner in cube.bound_box]
        xmin = min([v.x for v in bbox_corners])
        xmax = max([v.x for v in bbox_corners])
        ymin = min([v.y for v in bbox_corners])
        ymax = max([v.y for v in bbox_corners])
        zmin = min([v.z for v in bbox_corners])
        zmax = max([v.z for v in bbox_corners])

        # Store extents in the scene properties
        self.xmin = xmin
        self.xmax = xmax
        self.ymin = ymin
        self.ymax = ymax
        self.zmin = zmin
        self.zmax = zmax
    else:
        self.xmin = self.xmax = self.ymin = self.ymax = self.zmin = self.zmax = 0
        
def get_collection_items(self, context):
    return [(col.name, col.name, "") for col in bpy.data.collections]

def update_formations_collection(self, context):
    collection_name = self.formations_collection
    if collection_name:
        create_formations_csv(collection_name)
        
def create_formations_csv(collection_name):
    col = bpy.data.collections.get(collection_name)
    if not col:
        print(f"Collection '{collection_name}' not found.")
        return

    data = []
    for obj in col.objects:
        coords = []
        formation_name = re.sub(r"\.\d+$", "", obj.name)  # Standardize name format
        formation_name = re.sub(r"\.$", "", formation_name)
        
        if obj.type == 'CURVE':
            curve = obj.data
            if curve.splines and len(curve.splines[0].points) >= 2:
                spline = curve.splines[0]
                points = spline.points if hasattr(spline, 'points') else spline.bezier_points
                low_point = min(points, key=lambda p: p.co.z)
                coords = low_point.co[:3]  # Ignore the 'w' for NURBS
        elif obj.type == 'MESH' and len(obj.data.vertices) > 0:
            coords = obj.location  # XYZ location for mesh data
        else:
            print(f"Object '{obj.name}' is not a curve with two points or a mesh with vertices.")
            continue

        data.append([formation_name] + list(coords))

    df = pd.DataFrame(data, columns=['formation', 'x', 'y', 'z'])
    blend_file_dir = os.path.dirname(bpy.data.filepath) or tempfile.gettempdir()
    csv_path = os.path.join(blend_file_dir, f"{collection_name}_formations.csv")
    df.to_csv(csv_path, index=False)
    print(f"CSV created at {csv_path}")


def load_unique_formations_into_properties(collection_name):
    blend_file_dir = os.path.dirname(bpy.data.filepath) or tempfile.gettempdir()
    csv_path = os.path.join(blend_file_dir, f"{collection_name}_formations.csv")
    df = pd.read_csv(csv_path)
    unique_formations = df['formation'].unique()
    bpy.context.scene.geo_modeller.formation_items.clear()
    for formation in unique_formations:
        item = bpy.context.scene.geo_modeller.formation_items.add()
        item.name = formation


def update_orientations_collection(self, context):
    collection_name = self.orientations_collection
    if collection_name:
        create_orientations_csv(collection_name)


def create_orientations_csv(collection_name):
    col = bpy.data.collections.get(collection_name)
    if not col:
        print(f"Collection '{collection_name}' not found.")
        return

    data = []
    geo_props = bpy.context.scene.geo_modeller
    
    for obj in col.objects:
        coords = []
        formation_name = re.sub(r"\.\d+$", "", obj.name)  # Standardize name format
        formation_name = re.sub(r"\.$", "", formation_name)
        
        if obj.type == 'CURVE':
            curve = obj.data
            if curve.splines and len(curve.splines[0].points) >= 2:
                spline = curve.splines[0]
                points = spline.points if hasattr(spline, 'points') else spline.bezier_points
                low_point = min(points, key=lambda p: p.co.z)
                coords = low_point.co[:3]  # Ignore the 'w' component for NURBS
        elif obj.type == 'MESH' and len(obj.data.vertices) > 0:
            coords = obj.location  
        
        if coords:
            polarity = float(obj.get('polarity', 1.0))  # Default to 1.0 if not set
            azimuth = float(obj.get('azimuth', 0.0))  # Convert to float and default to 0.0 if not set
            dip = float(obj.get('dip', 0.0)) # Convert to float and default to 0.0 if not set
            
            if geo_props.orientation_mode == 'RIGHT_HAND_RULE':
                azimuth = (azimuth + 90) % 360
            
            data.append([formation_name] + list(coords) + [polarity, azimuth, dip])
        else:
            print(f"Object '{obj.name}' is not a curve with two points or a mesh with vertices.")
            continue

    df = pd.DataFrame(data, columns=['formation', 'x', 'y', 'z', 'polarity', 'azimuth', 'dip'])
    blend_file_dir = os.path.dirname(bpy.data.filepath) or tempfile.gettempdir()
    csv_path = os.path.join(blend_file_dir, f"{collection_name}_orientations.csv")
    df.to_csv(csv_path, index=False)
    print(f"CSV created at {csv_path}")


class StratSeriesItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    selected: bpy.props.BoolProperty(default=False)

class StratSeriesGroup(bpy.types.PropertyGroup):
    items: bpy.props.CollectionProperty(type=StratSeriesItem)
    order: bpy.props.IntProperty(name="Order", default=0, min=0, description="Order of the series, 0 being the youngest")
    unique_id: bpy.props.StringProperty()
    series_type: bpy.props.StringProperty(default="Strat_Series")
    
    # Add the EnumProperty for selecting the relation type
    relation_type: bpy.props.EnumProperty(
        name="Relation Type",
        description="Choose the type of relation for this strat series",
        items=[
            ('ERODE', "Erode", "Set as erode relation"),
            ('ONLAP', "Onlap", "Set as onlap relation"),
            ('BASEMENT', "Basement", "Set as basement relation")
        ],
        default='ERODE'
    )


class LoadFormationsOperator(bpy.types.Operator):
    bl_idname = "object.load_formations"
    bl_label = "Add Strat Series"

    def execute(self, context):
        new_group = context.scene.geo_modeller.strat_series_groups.add()
        new_group.series_type = "Strat_Series"
        new_group.unique_id = f"A{len(context.scene.geo_modeller.strat_series_groups)}"
        geo_props = context.scene.geo_modeller
        
        blend_file_dir = os.path.dirname(bpy.data.filepath) or tempfile.gettempdir()
        csv_path = os.path.join(blend_file_dir, f"{geo_props.formations_collection}_formations.csv")
        
        if csv_path:
            try:
                df = pd.read_csv(csv_path)
                unique_formations = df['formation'].unique()
                for formation_name in unique_formations:
                    item = new_group.items.add()
                    item.name = formation_name
                    item.selected = False
                self.report({'INFO'}, "New Strat Series added")
            except Exception as e:
                self.report({'ERROR'}, f"Failed to read CSV: {str(e)}")
        else:
            self.report({'ERROR'}, "No formations CSV specified")
        return {'FINISHED'}


class FaultSeriesItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    selected: bpy.props.BoolProperty(default=False)


class FaultSeriesGroup(bpy.types.PropertyGroup):
    items: bpy.props.CollectionProperty(type=FaultSeriesItem)
    order: bpy.props.IntProperty(name="Order", default=0, min=0, description="Order of the series, 1 being the youngest")
    unique_id: bpy.props.StringProperty()
    series_type: bpy.props.StringProperty(default="Fault_Series")


class AddFaultSeriesOperator(bpy.types.Operator):
    bl_idname = "object.add_fault_series"
    bl_label = "Add Fault Series"

    def execute(self, context):
        new_group = context.scene.geo_modeller.fault_series_groups.add()
        new_group.series_type = "Fault_Series"
        new_group.unique_id = f"B{len(context.scene.geo_modeller.fault_series_groups)}"
        geo_props = context.scene.geo_modeller
        
        blend_file_dir = os.path.dirname(bpy.data.filepath) or tempfile.gettempdir()
        csv_path = os.path.join(blend_file_dir, f"{geo_props.orientations_collection}_orientations.csv")
        
        if csv_path:
            try:
                df = pd.read_csv(csv_path)
                unique_formations = df['formation'].unique()
                for formation_name in unique_formations:
                    item = new_group.items.add()
                    item.name = formation_name
                    item.selected = False
                self.report({'INFO'}, "New Fault Series added")
            except Exception as e:
                self.report({'ERROR'}, f"Failed to read CSV: {str(e)}")
        else:
            self.report({'ERROR'}, "No orientations CSV specified")
        return {'FINISHED'}


class RemoveStratSeriesOperator(bpy.types.Operator):
    bl_idname = "geo.remove_strat_series"
    bl_label = "Remove Strat Series"
    index: bpy.props.IntProperty()

    def execute(self, context):
        geo_modeller_props = context.scene.geo_modeller
        if len(geo_modeller_props.strat_series_groups) > self.index:
            geo_modeller_props.strat_series_groups.remove(self.index)
            self.report({'INFO'}, "Strat Series removed")
        else:
            self.report({'ERROR'}, "Invalid series index")
        return {'FINISHED'}
        

class RemoveFaultSeriesOperator(bpy.types.Operator):
    bl_idname = "geo.remove_fault_series"
    bl_label = "Remove Fault Series"
    index: bpy.props.IntProperty()

    def execute(self, context):
        geo_modeller_props = context.scene.geo_modeller
        if len(geo_modeller_props.fault_series_groups) > self.index:
            geo_modeller_props.fault_series_groups.remove(self.index)
            self.report({'INFO'}, "Fault Series removed")
        else:
            self.report({'ERROR'}, "Invalid series index")
        return {'FINISHED'}


class SeriesItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    selected: bpy.props.BoolProperty(default=False)
    order: bpy.props.IntProperty(name="Order", default=0, min=0, description="Order of geological events, 1 being the youngest")


class GeoModellerProperties(bpy.types.PropertyGroup):
    cube_object: bpy.props.PointerProperty(
        name="Cube Object",
        type=bpy.types.Object,
        description="Select a cube object to define extents",
        poll=lambda self, obj: obj.type == 'MESH',
        update=update_cube_extents
    )
    xmin: bpy.props.FloatProperty(name="X Min")
    xmax: bpy.props.FloatProperty(name="X Max")
    ymin: bpy.props.FloatProperty(name="Y Min")
    ymax: bpy.props.FloatProperty(name="Y Max")
    zmin: bpy.props.FloatProperty(name="Z Min")
    zmax: bpy.props.FloatProperty(name="Z Max")
    project_name: bpy.props.StringProperty(
        name="Project Name",
        description="Enter the project name"
    )
    refinement: bpy.props.IntProperty(
        name="Refinement",
        description="Enter number of refinements",
        default=6,
        min=1, max=10
    )
    formations_collection: bpy.props.EnumProperty(
        name="Formations Collection",
        description="Select a collection for formations data",
        items=get_collection_items,
        update=update_formations_collection
    )
    orientations_collection: bpy.props.EnumProperty(
        name="Orientations Collection",
        description="Select a collection for orientations data",
        items=get_collection_items,
        update=update_orientations_collection
    )
    strat_series_groups: bpy.props.CollectionProperty(type=StratSeriesGroup)
    fault_series_groups: bpy.props.CollectionProperty(type=FaultSeriesGroup)
    orientation_mode: bpy.props.EnumProperty(
        name="Orientation Mode",
        description="Choose the orientation mode for azimuth and dip",
        items=[
            ('DIP_DIRECTION', "Dip Direction", "Use dip direction for azimuth and dip"),
            ('RIGHT_HAND_RULE', "Right Hand Rule", "Use right hand rule for azimuth and dip")
        ],
        default='DIP_DIRECTION'
    )


class OBJECT_PT_GeoModeller(bpy.types.Panel):
    bl_label = "GemPy Modeller"
    bl_idname = "OBJECT_PT_geo_modeller"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'GeoModeller'
    bl_parent_id = "GEOMOD_PT_geologic_models_category"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        geo_modeller_props = context.scene.geo_modeller

        layout.label(text="📏 Extents Settings:")
        layout.prop(geo_modeller_props, "cube_object", text="Extents Object")

        layout.label(text="🛠️ Project Settings:")
        layout.prop(geo_modeller_props, "project_name", text="Project Name")
        layout.prop(geo_modeller_props, "refinement", text="Refinement")
        
        layout.label(text="Data Uses:")
        layout.prop(geo_modeller_props, "orientation_mode", expand=True)

        layout.label(text="📚 Use Blender Collection:")
        layout.prop(geo_modeller_props, "formations_collection", text="Formations Collection")
        layout.prop(geo_modeller_props, "orientations_collection", text="Orientations Collection")
        

        layout.label(text="⚙️ Build Parameters")
        layout.operator("object.load_formations", text="Add Strat Series")

        for idx, series_group in enumerate(geo_modeller_props.strat_series_groups):
            box = layout.box()
            box.label(text=f"Strat Series {idx + 1} - Order: {series_group.order}")
            row = box.row()
            row.prop(series_group, "order", text="Order")
            row.prop(series_group, "relation_type", text="Relation")
            for item in series_group.items:
                row = box.row()
                row.prop(item, "selected", text=item.name)
            remove_op = box.operator("geo.remove_strat_series", text="Remove This Series", icon='X')
            remove_op.index = idx

        layout.operator("object.add_fault_series", text="Add Fault Series")
        for idx, series_group in enumerate(geo_modeller_props.fault_series_groups):
            box = layout.box()
            box.label(text=f"Fault Series {idx + 1} - Order: {series_group.order}")
            row = box.row()
            row.prop(series_group, "order", text="Order")
            for item in series_group.items:
                row = box.row()
                row.prop(item, "selected", text=item.name)
            remove_op = box.operator("geo.remove_fault_series", text="Remove This Fault Series", icon='X')
            remove_op.index = idx

        layout.operator("object.compute_gempy_model", text="Compute Model", icon='PLAY')


def get_ordered_series_dict(context):
    series_dict = {}
    identifier_counter = {}

    for group in list(context.scene.geo_modeller.strat_series_groups):
        update_series_dict(group, 'Strat_Series', series_dict, identifier_counter)

    for group in list(context.scene.geo_modeller.fault_series_groups):
        update_series_dict(group, 'Fault_Series', series_dict, identifier_counter)
        
    sorted_keys = sorted(series_dict.keys(), key=lambda x: (int(x.split('Series')[1][1:]), x))
    series_dict = {key: series_dict[key] for key in sorted_keys}

    return series_dict
    

def update_series_dict(group, series_type, series_dict, identifier_counter):
    if series_type not in identifier_counter:
        identifier_counter[series_type] = 0

    identifier = string.ascii_uppercase[identifier_counter[series_type] % 26]
    identifier_counter[series_type] += 1

    for item in group.items:
        if item.selected:
            series_key = f"{series_type}{identifier}{group.order}"
            if series_key in series_dict:
                series_dict[series_key].append(item.name)
            else:
                series_dict[series_key] = [item.name]


def create_fault_relations_from_dict(series_dict):

    def extract_order(key):
        parts = key.split('Series')
        order_part = ''.join(filter(str.isdigit, parts[-1]))
        return int(order_part)

    sorted_keys = sorted(series_dict.keys(), key=lambda x: extract_order(x))
    n = len(sorted_keys)

    fault_relations = np.zeros((n, n), dtype=int)

    for i, key_i in enumerate(sorted_keys):
        for j in range(i + 1, n):
            if 'Fault_Series' in key_i:
                fault_relations[i, j] = 1

    return fault_relations


def initialize_gempy_from_blender(geo_props):
    extent = [geo_props.xmin, geo_props.xmax, geo_props.ymin, geo_props.ymax, geo_props.zmin, geo_props.zmax] # extent from cube object
    
    blend_file_dir = os.path.dirname(bpy.data.filepath) or tempfile.gettempdir()
    formations_csv = os.path.join(blend_file_dir, f"{geo_props.formations_collection}_formations.csv")
    orientations_csv = os.path.join(blend_file_dir, f"{geo_props.orientations_collection}_orientations.csv")

    data = gp.create_geomodel(
        project_name=geo_props.project_name,
        extent=extent,
        refinement=geo_props.refinement,
        importer_helper=gp.data.ImporterHelper(
            path_to_orientations=orientations_csv,
            path_to_surface_points=formations_csv
        )
    )
    return data
    
    
def map_series_to_surfaces_and_set_relations(data, series_dict):
    gp.map_stack_to_surfaces(
        gempy_model=data,
        mapping_object=series_dict
    )
    print("Mapping geological series to surfaces using:", series_dict)

    fault_relations_matrix = create_fault_relations_from_dict(series_dict)

    strat_series_groups = bpy.context.scene.geo_modeller.strat_series_groups
    strat_series_index = 0  # Track the index separately for strat series

    for idx, (key, series_names) in enumerate(series_dict.items()):
        group = data.structural_frame.structural_groups[idx]

        # Check if this is a strat series or a fault series
        if 'Strat_Series' in key and strat_series_index < len(strat_series_groups):
            series_group = strat_series_groups[strat_series_index]

            # Set structural relation based on user selection
            if series_group.relation_type == 'ERODE':
                group.structural_relation = StackRelationType.ERODE
            elif series_group.relation_type == 'ONLAP':
                group.structural_relation = StackRelationType.ONLAP
            elif series_group.relation_type == 'BASEMENT':
                group.structural_relation = StackRelationType.BASEMENT
            
            print(f"Set {series_group.relation_type} relation for series at index {idx}: {series_names}")
            strat_series_index += 1
        elif 'Fault_Series' in key:
            group.structural_relation = StackRelationType.FAULT
            print(f"Set Fault relation for series at index {idx}: {series_names}")
        else:
            print(f"Warning: No matching strat series group for structural group at index {idx}")

    if any('Fault_Series' in key for key in series_dict):
        data.structural_frame.fault_relations = fault_relations_matrix
        print("Fault relations matrix set:", fault_relations_matrix)
    else:
        print("No fault series selected, proceeding without setting fault relations.")

    print(data.structural_frame)


class ComputeGemPyModelOperator(bpy.types.Operator):
    bl_idname = "object.compute_gempy_model"
    bl_label = "Compute GemPy Model"

    def execute(self, context):
        geo_props = context.scene.geo_modeller
        data = initialize_gempy_from_blender(geo_props)
        series_dict = get_ordered_series_dict(context)
        
        map_series_to_surfaces_and_set_relations(data, series_dict)
        
        compute_and_visualize_model(data)
        self.report({'INFO'}, "GemPy Model Computed and ready for visualization")
        return {'FINISHED'}

def compute_and_visualize_model(data): # This part is post-gempy module. this creates the mesh from the raw-arrays
    # Compute the geological model
    gp.compute_model(data)
    
    # Access the vertices and edges directly from the solutions object
    all_vertices = data.solutions.raw_arrays.vertices
    all_edges = data.solutions.raw_arrays.edges

    # Ensure Blender's context is appropriate
    scene = bpy.context.scene

    # Get project name and create a unique collection for the project
    project_name = scene.geo_modeller.project_name
    base_collection_name = project_name
    collection_name = base_collection_name
    count = 1
    
    while collection_name in bpy.data.collections:
        collection_name = f"{base_collection_name}_{count}"
        count += 1
    
    project_collection = bpy.data.collections.new(collection_name)
    scene.collection.children.link(project_collection)

    # Collect series names and colors from all structural group elements
    series_elements = []
    for group in data.structural_frame.structural_groups:
        for element in group.elements:
            series_elements.append((element.name, element.color))

    for i, (vertices, (name, color)) in enumerate(zip(all_vertices, series_elements)):
        # Apply the inverse transformation to each set of vertices
        transformed_vertices = data.transform.apply_inverse(vertices)

        # Create a new mesh and object for each set of transformed vertices
        mesh = bpy.data.meshes.new(f'Surface_{name}')
        obj = bpy.data.objects.new(f'Surface_{name}', mesh)

        # Link object to the project collection
        project_collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        # Use BMesh to construct the mesh
        bm = bmesh.new()
        for vert in transformed_vertices:
            bm.verts.new((vert[0], vert[1], vert[2]))
        bm.verts.ensure_lookup_table()

        # Add edges or faces to BMesh
        if i < len(all_edges):
            edges = all_edges[i]
            for edge in edges:
                try:
                    bm.faces.new((bm.verts[edge[0]], bm.verts[edge[1]], bm.verts[edge[2]]))
                except ValueError:
                    continue

        bm.to_mesh(mesh)
        bm.free()  

        # Set object color using shader nodes
        material = bpy.data.materials.new(name=f"Material_{name}")
        material.use_nodes = True
        bsdf = material.node_tree.nodes.get("Principled BSDF")

        if bsdf:
            bsdf.inputs['Base Color'].default_value = (*[int(color[i:i+2], 16)/255 for i in (1, 3, 5)], 1)

        obj.data.materials.append(material)

    print("Model computation and visualization complete.")


       
def register():
    bpy.utils.register_class(StratSeriesItem)
    bpy.utils.register_class(StratSeriesGroup)
    bpy.utils.register_class(FaultSeriesItem)
    bpy.utils.register_class(FaultSeriesGroup)
    bpy.utils.register_class(GeoModellerProperties)
    bpy.types.Scene.geo_modeller = bpy.props.PointerProperty(type=GeoModellerProperties)
    
    bpy.utils.register_class(RemoveStratSeriesOperator)
    bpy.utils.register_class(RemoveFaultSeriesOperator)
    bpy.utils.register_class(AddFaultSeriesOperator)
    bpy.utils.register_class(LoadFormationsOperator)
    bpy.utils.register_class(ComputeGemPyModelOperator)
    bpy.utils.register_class(OBJECT_PT_GeoModeller)

def unregister():
    bpy.utils.unregister_class(OBJECT_PT_GeoModeller)
    bpy.utils.unregister_class(ComputeGemPyModelOperator)
    bpy.utils.unregister_class(LoadFormationsOperator)
    bpy.utils.unregister_class(AddFaultSeriesOperator)
    bpy.utils.unregister_class(RemoveFaultSeriesOperator)
    bpy.utils.unregister_class(RemoveStratSeriesOperator)
    
    del bpy.types.Scene.geo_modeller
    bpy.utils.unregister_class(GeoModellerProperties)
    bpy.utils.unregister_class(FaultSeriesGroup)
    bpy.utils.unregister_class(FaultSeriesItem)
    bpy.utils.unregister_class(StratSeriesGroup)
    bpy.utils.unregister_class(StratSeriesItem)

if __name__ == "__main__":
    register()

