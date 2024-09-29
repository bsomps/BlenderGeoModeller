import bpy
import math
from mathutils import Vector
from bpy.types import Panel, Operator, PropertyGroup
from bpy.props import FloatProperty, BoolProperty
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

            # Correct the azimuth and plunge to work with blender 
            azimuth_corrected = (azimuth + 180) % 360
            plunge_corrected = plunge

            azimuth_rad = math.radians(azimuth_corrected)
            plunge_rad = math.radians(plunge_corrected)

            view_vector = Vector((math.cos(plunge_rad) * math.sin(azimuth_rad),
                                  math.cos(plunge_rad) * math.cos(azimuth_rad),
                                  math.sin(plunge_rad)))

            # Set the view rotation using the computed view vector
            rv3d.view_rotation = view_vector.to_track_quat('Z', 'Y')

            break


class ViewDirectionProperties(PropertyGroup):
    azimuth: FloatProperty(
        name="Set Azimuth",
        description="Azimuth angle in degrees",
        default=0.0,
        min=0.0,
        max=360.0,
    )

    plunge: FloatProperty(
        name="Set Plunge",
        description="Plunge angle in degrees",
        default=0.0,
        min=-90.0,
        max=90.0,
    )

    set_manually: BoolProperty(
        name="Set Manually",
        description="Enable manual input for azimuth and plunge",
        default=False,
    )


class VIEWDIRECTION_PT_Panel(Panel):
    bl_label = "View Direction"
    bl_idname = "GEOMOD_PT_view_direction"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'GeoModeller'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        view_props = context.scene.view_direction_props

        azimuth, plunge = get_view_direction_azimuth_and_plunge(context)

        if azimuth is not None and plunge is not None:
            layout.label(text=f"Viewing Azimuth: {azimuth:.2f}°")
            layout.label(text=f"Plunge: {plunge:.2f}°")
        else:
            layout.label(text="No active 3D view")

        layout.prop(view_props, "set_manually")

        if view_props.set_manually:
            layout.prop(view_props, "azimuth")
            layout.prop(view_props, "plunge")
            layout.operator("view3d.set_view_direction", text="Apply")


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
    bpy.utils.register_class(VIEWDIRECTION_OT_SetOperator)
    bpy.utils.register_class(ViewDirectionProperties)
    bpy.types.Scene.view_direction_props = bpy.props.PointerProperty(type=ViewDirectionProperties)
    bpy.app.handlers.load_post.append(load_handler)


def unregister():
    bpy.utils.unregister_class(VIEWDIRECTION_PT_Panel)
    bpy.utils.unregister_class(VIEWDIRECTION_OT_SetOperator)
    bpy.utils.unregister_class(ViewDirectionProperties)
    del bpy.types.Scene.view_direction_props
    bpy.app.handlers.load_post.remove(load_handler)


if __name__ == "__main__":
    register()
