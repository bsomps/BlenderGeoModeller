import bpy
from . import preferences  

bl_info = {
    "name": "GeoModeller",
    "author": "Bsomps",
    "version": (1, 0, 0),
    "blender": (4, 1, 0),
    "location": "View3D > Sidebar > GeoModeller",
    "description": "A comprehensive toolset for geological modelling in Blender",
    "category": "3D View"
}

class GEOMOD_PT_drilling_category(bpy.types.Panel):
    """Main panel for drilling category"""
    bl_label = "Drilling"
    bl_idname = "GEOMOD_PT_drilling_category"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'GeoModeller'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.label(text="Select an operation:")

class GEOMOD_PT_geologic_models_category(bpy.types.Panel):
    """Main panel for geological models category"""
    bl_label = "Geological Modelling"
    bl_idname = "GEOMOD_PT_geologic_models_category"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'GeoModeller'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.label(text="Select an operation:")
        
class GEOMOD_PT_numerical_models_category(bpy.types.Panel):
    """Main panel for numerical models category"""
    bl_label = "Numerical Modelling"
    bl_idname = "GEOMOD_PT_numerical_models_category"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'GeoModeller'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.label(text="Select an operation:")

class GEOMOD_PT_points_category(bpy.types.Panel):
    """Main panel for point data"""
    bl_label = "Point Data"
    bl_idname = "GEOMOD_PT_points_category"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'GeoModeller'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.label(text="Select an operation:")
    

def register():
    print("Registering GeoModeller panels")
    bpy.utils.register_class(GEOMOD_PT_drilling_category)
    bpy.utils.register_class(GEOMOD_PT_points_category)
    bpy.utils.register_class(GEOMOD_PT_geologic_models_category)
    bpy.utils.register_class(GEOMOD_PT_numerical_models_category)
    
    
    preferences.register()

    from .Drilling import bldesurvey
    from .Drilling import import_drill_holes  
    from .Drilling import drill_hole_planner
    from .Geological_Modelling import gempy_model
    from .Drilling import manage_drill_holes
    from .Drilling import drill_hole_query
    from .Numerical_Modelling import RBF_interpolant
    from .Numerical_Modelling import RBF_block_model
    from .Section_Slicer import section_slicer
    from .View_Direction import view_direction
    from .Point_Data import add_points
    from .Point_Data import points_manager
    from .Point_Data import point_data_query
    from .Geological_Modelling import strc_planes
    from .Geological_Modelling import strc_discs
    
    bldesurvey.register()
    import_drill_holes.register()
    gempy_model.register()
    manage_drill_holes.register()
    drill_hole_query.register()
    drill_hole_planner.register()
    RBF_interpolant.register()
    RBF_block_model.register()
    section_slicer.register()
    view_direction.register()
    add_points.register()
    points_manager.register()
    point_data_query.register()
    strc_planes.register()
    strc_discs.register()

def unregister():
    print("Unregistering GeoModeller panels")
    
    classes = [
        GEOMOD_PT_drilling_category,
        GEOMOD_PT_points_category,
        GEOMOD_PT_geologic_models_category,
        GEOMOD_PT_numerical_models_category
    ]
    
    for cls in classes:
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
    
    preferences.unregister()

    from .Drilling import bldesurvey
    from .Drilling import import_drill_holes  
    from .Drilling import drill_hole_planner
    from .Geological_Modelling import gempy_model
    from .Drilling import manage_drill_holes
    from .Drilling import drill_hole_query
    from .Numerical_Modelling import RBF_interpolant
    from .Numerical_Modelling import RBF_block_model
    from .Section_Slicer import section_slicer
    from .View_Direction import view_direction
    from .Point_Data import add_points
    from .Point_Data import points_manager
    from .Point_Data import point_data_query
    from .Geological_Modelling import strc_planes
    from .Geological_Modelling import strc_discs
    
    bldesurvey.unregister()
    import_drill_holes.unregister()
    gempy_model.unregister()
    manage_drill_holes.unregister()
    drill_hole_query.unregister()
    drill_hole_planner.unregister()
    RBF_interpolant.unregister()
    RBF_block_model.unregister()
    section_slicer.unregister()
    view_direction.unregister()
    add_points.unregister()
    points_manager.unregister()
    point_data_query.unregister()
    strc_planes.unregister()
    strc_discs.unregister()

if __name__ == "__main__":
    register()
