import bpy
import math
from mathutils import Vector
from bpy.types import Panel, Operator, PropertyGroup
from bpy.props import FloatProperty, BoolProperty, PointerProperty
from bpy.app.handlers import persistent




def get_view_direction_azimuth_and_plunge(context):
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            rv3d = area.spaces.active.region_3d
            if rv3d is None or rv3d.view_rotation is None:
                continue

            view_vector = rv3d.view_rotation @ Vector((0.0, 0.0, -1.0))
            azimuth = (math.degrees(math.atan2(view_vector.x, view_vector.y)) + 360) % 360
            plunge = math.degrees(math.asin(-view_vector.z))

            return azimuth, plunge

    return None, None


def set_view_direction(context, azimuth, plunge):
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            rv3d = area.spaces.active.region_3d
            if rv3d is None:
                continue

            azimuth_corrected = (azimuth + 180) % 360
            plunge_corrected = plunge

            azimuth_rad = math.radians(azimuth_corrected)
            plunge_rad = math.radians(plunge_corrected)

            view_vector = Vector((math.cos(plunge_rad) * math.sin(azimuth_rad),
                                  math.cos(plunge_rad) * math.cos(azimuth_rad),
                                  math.sin(plunge_rad)))

            rv3d.view_rotation = view_vector.to_track_quat('Z', 'Y')

            break

def get_scene_offset():
    scene = bpy.context.scene
    offset_x = scene.get('crs x', 0)
    offset_y = scene.get('crs y', 0)
    offset_z = 0  
    return offset_x, offset_y, offset_z


def create_empty(name, location, collection):
    empty = bpy.data.objects.new(name, None)
    empty.matrix_world.translation = location
    empty.show_name = True  # name is visible

    
    collection.objects.link(empty)

    
    if empty.name in bpy.context.scene.collection.objects:
        bpy.context.scene.collection.objects.unlink(empty)

    return empty


def distribute_empties_on_selected_axes(obj, spacing_x, spacing_y, spacing_z, show_x, show_y, show_z):
    
    if obj.type != 'MESH':
        print("Selected object is not a mesh.")
        return

    collection_name = "Tick Markers"
    if collection_name in bpy.data.collections:
        collection = bpy.data.collections[collection_name]
    else:
        collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(collection)

    offset_x, offset_y, offset_z = get_scene_offset()
    world_matrix = obj.matrix_world
    bbox_corners = [world_matrix @ Vector(corner) for corner in obj.bound_box]

    
    origin = min(bbox_corners, key=lambda v: (v.x, v.y, v.z))

    
    edges = [
        (0, 1), (1, 2), (2, 3), (3, 0),  # Bottom edges
        (4, 5), (5, 6), (6, 7), (7, 4),  # Top edges
        (0, 4), (1, 5), (2, 6), (3, 7)   # Vertical edges
    ]

    
    for obj in list(collection.objects):
        if obj.type == 'EMPTY':
            bpy.data.objects.remove(obj, do_unlink=True)

    
    def interpolate_points(v1, v2, spacing):
        
        #Generate points along an edge at a user-given spacing.
        edge_length = (v2 - v1).length
        num_points = max(1, int(edge_length // spacing))  # Ensure at least 1 point
        return [v1.lerp(v2, i / num_points) for i in range(num_points + 1)]

    
    edges_from_origin = []
    for start_idx, end_idx in edges:
        v1 = bbox_corners[start_idx]
        v2 = bbox_corners[end_idx]

        if v1 == origin:
            edges_from_origin.append((v1, v2))
        elif v2 == origin:
            edges_from_origin.append((v2, v1))

    origin_added = False

    for v1, v2 in edges_from_origin:
        if abs(v1.x - v2.x) > abs(v1.y - v2.y) and abs(v1.x - v2.x) > abs(v1.z - v2.z):
            spacing = spacing_x
            label_suffix = "E"
            show = show_x
        elif abs(v1.y - v2.y) > abs(v1.z - v2.z):
            spacing = spacing_y
            label_suffix = "N"
            show = show_y
        else:
            spacing = spacing_z
            label_suffix = "m"
            show = show_z

        if show:
            points = interpolate_points(v1, v2, spacing)

            for point in points:
                name = f"{int(point.x + offset_x) if label_suffix == 'E' else int(point.y + offset_y) if label_suffix == 'N' else int(point.z + offset_z)}{label_suffix}"
                if point == origin and origin_added:
                    continue
                create_empty(name, point, collection)
                if point == origin:
                    origin_added = True


class ViewDirectionProperties(PropertyGroup):
    selected_object: PointerProperty(
        name="Target Object",
        type=bpy.types.Object,
        description="Select the cube object to generate coordinate ticks"
    )

    enable_coordinate_markers: BoolProperty(
        name="Create Coordinate Markers",
        description="Enable coordinate marker creation",
        default=False
    )

    spacing_x: FloatProperty(name="X-Axis Spacing", default=150.0, min=1.0)
    spacing_y: FloatProperty(name="Y-Axis Spacing", default=150.0, min=1.0)
    spacing_z: FloatProperty(name="Z-Axis Spacing", default=150.0, min=1.0)

    show_x: BoolProperty(name="Show X-Axis Ticks", default=True)
    show_y: BoolProperty(name="Show Y-Axis Ticks", default=True)
    show_z: BoolProperty(name="Show Z-Axis Ticks", default=True)

    azimuth: FloatProperty(name="Set Azimuth", default=0.0, min=0.0, max=360.0)
    plunge: FloatProperty(name="Set Plunge", default=0.0, min=-90.0, max=90.0)
    set_manually: BoolProperty(name="Set Manually", default=False)


class VIEWDIRECTION_PT_Panel(Panel):
    bl_label = "View & Grid Tools"
    bl_idname = "GEOMOD_PT_view_direction"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'GeoModeller'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        view_props = context.scene.view_direction_props

        azimuth, plunge = get_view_direction_azimuth_and_plunge(context)
        layout.label(text=f"Viewing Azimuth: {azimuth:.2f}°" if azimuth is not None else "No active 3D view")
        layout.label(text=f"Plunge: {plunge:.2f}°" if plunge is not None else "")

        layout.prop(view_props, "set_manually")
        if view_props.set_manually:
            layout.prop(view_props, "azimuth")
            layout.prop(view_props, "plunge")
            layout.operator("view3d.set_view_direction", text="Apply")

        layout.separator()

        layout.prop(view_props, "enable_coordinate_markers")
        if view_props.enable_coordinate_markers:
            layout.prop(view_props, "selected_object")
            layout.prop(view_props, "spacing_x")
            layout.prop(view_props, "spacing_y")
            layout.prop(view_props, "spacing_z")
            layout.prop(view_props, "show_x")
            layout.prop(view_props, "show_y")
            layout.prop(view_props, "show_z")
            layout.operator("view3d.create_coordinate_ticks", text="Create Coordinate Ticks")

class VIEWDIRECTION_OT_CreateTicks(Operator):
    bl_idname = "view3d.create_coordinate_ticks"
    bl_label = "Create Coordinate Ticks"

    def execute(self, context):
        view_props = context.scene.view_direction_props
        obj = view_props.selected_object

        if obj and obj.type == 'MESH':
            distribute_empties_on_selected_axes(
                obj, view_props.spacing_x, view_props.spacing_y, view_props.spacing_z,
                view_props.show_x, view_props.show_y, view_props.show_z
            )
            self.report({'INFO'}, "Coordinate ticks created successfully.")
        else:
            self.report({'WARNING'}, "Select a cube object first.")
        return {'FINISHED'}
        
        
class VIEWDIRECTION_OT_SetOperator(Operator):
    bl_idname = "view3d.set_view_direction"
    bl_label = "Set View Direction"

    def execute(self, context):
        view_props = context.scene.view_direction_props
        set_view_direction(context, view_props.azimuth, view_props.plunge)
        return {'FINISHED'}


@persistent
def load_handler(dummy):
    pass  

def register():
    bpy.utils.register_class(VIEWDIRECTION_PT_Panel)
    bpy.utils.register_class(VIEWDIRECTION_OT_CreateTicks)
    bpy.utils.register_class(VIEWDIRECTION_OT_SetOperator)
    bpy.utils.register_class(ViewDirectionProperties)
    bpy.types.Scene.view_direction_props = bpy.props.PointerProperty(type=ViewDirectionProperties)


def unregister():
    bpy.utils.unregister_class(VIEWDIRECTION_PT_Panel)
    bpy.utils.unregister_class(VIEWDIRECTION_OT_CreateTicks)
    bpy.utils.unregister_class(VIEWDIRECTION_OT_SetOperator)
    bpy.utils.unregister_class(ViewDirectionProperties)
    del bpy.types.Scene.view_direction_props


if __name__ == "__main__":
    register()
