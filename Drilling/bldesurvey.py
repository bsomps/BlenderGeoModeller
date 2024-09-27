import bpy
import pandas as pd
import numpy as np


# Global variables to store the loaded data
drill_data = pd.DataFrame()
survey_data = pd.DataFrame()
collar_data = pd.DataFrame()

def update_drill_columns(self, context):
    return [(col, col, "") for col in context.scene.drill_columns.split(',') if col]

def update_survey_columns(self, context):
    return [(col, col, "") for col in context.scene.survey_columns.split(',') if col]

def update_collar_columns(self, context):
    columns = context.scene.collar_columns.split(',')
    items = [('None', 'None', 'None')] + [(col, col, "") for col in columns if col] # None for setting start depth to 0
    return items

class ContinuousDesurveyCalcPanel(bpy.types.Panel):
    bl_label = "Desurvey Data"
    bl_idname = "VIEW3D_PT_desurvey_calc"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'GeoModeller'  
    bl_parent_id = "GEOMOD_PT_drilling_category"  
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        # Drill hole data
        layout.operator("desurvey.upload_drill_data", text="Upload Drill Hole Data", icon='FILE')

        # Select columns for drill data
        layout.label(text="Select Columns for Drill Hole Data")
        layout.prop(context.scene, "drill_hole_id")
        layout.prop(context.scene, "drill_from_depth")
        layout.prop(context.scene, "drill_to_depth")
        
        # Survey data
        layout.operator("desurvey.upload_survey_data", text="Upload Survey Data", icon='FILE')

        # Select columns for survey data
        layout.label(text="Select Columns for Survey Data")
        layout.prop(context.scene, "survey_hole_id")
        layout.prop(context.scene, "survey_depth")
        layout.prop(context.scene, "survey_azimuth")
        layout.prop(context.scene, "survey_dip")
        
        # Collar data
        layout.operator("desurvey.upload_collar_data", text="Upload Collar Data", icon='FILE')

        # Select columns for collar data
        layout.label(text="Select Columns for Collar Data")
        layout.prop(context.scene, "collar_hole_id")
        layout.prop(context.scene, "collar_easting")
        layout.prop(context.scene, "collar_northing")
        layout.prop(context.scene, "collar_elevation")
        layout.prop(context.scene, "collar_start_depth")
        layout.prop(context.scene, "collar_final_depth")

        # Get Desurveyed CSV
        layout.operator("desurvey.generate_csv", text="Get Desurveyed CSV", icon='PLAY')


class UploadDrillDataOperator(bpy.types.Operator):
    bl_idname = "desurvey.upload_drill_data"
    bl_label = "Upload Drill Data"

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        global drill_data
        drill_data = pd.read_csv(self.filepath)
        context.scene.drill_columns = ','.join(drill_data.columns)
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class UploadSurveyDataOperator(bpy.types.Operator):
    bl_idname = "desurvey.upload_survey_data"
    bl_label = "Upload Survey Data"

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        global survey_data
        survey_data = pd.read_csv(self.filepath)
        context.scene.survey_columns = ','.join(survey_data.columns)
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class UploadCollarDataOperator(bpy.types.Operator):
    bl_idname = "desurvey.upload_collar_data"
    bl_label = "Upload Collar Data"

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        global collar_data
        collar_data = pd.read_csv(self.filepath)
        context.scene.collar_columns = ','.join(collar_data.columns)
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class GenerateCSVOperator(bpy.types.Operator):
    bl_idname = "desurvey.generate_csv"
    bl_label = "Generate CSV"

    def execute(self, context):
        result_data = self.calculate_desurveyed_data(context)

        if not result_data.empty:
            # Show the file dialog after the calculation is done
            bpy.ops.desurvey.save_csv('INVOKE_DEFAULT')
        else:
            self.report({'WARNING'}, "Failed to generate desurveyed data!")

        return {'FINISHED'}

    def calculate_desurveyed_data(self, context):
        global drill_data, survey_data, collar_data
        
        # Extracting data from the UI elements
        hole_id_col_drill = context.scene.drill_hole_id
        from_depth_col_drill = context.scene.drill_from_depth
        to_depth_col_drill = context.scene.drill_to_depth
        
        hole_id_col_survey = context.scene.survey_hole_id
        depth_col_survey = context.scene.survey_depth
        azimuth_col_survey = context.scene.survey_azimuth
        dip_col_survey = context.scene.survey_dip

        hole_id_col_collar = context.scene.collar_hole_id
        easting_col_collar = context.scene.collar_easting
        northing_col_collar = context.scene.collar_northing
        elevation_col_collar = context.scene.collar_elevation
        start_depth_collar = 0 if context.scene.collar_start_depth == 'None' else context.scene.collar_start_depth
        final_depth_collar = context.scene.collar_final_depth
        
        # Ensure the data is sorted by 'hole_id' and 'to_depth'
        drill_data.sort_values(by=[hole_id_col_drill, to_depth_col_drill], inplace=True)
        drill_data.reset_index(drop=True, inplace=True)
        
        # Function to emulate the behavior of VLOOKUP with TRUE flag for approximate match.
        def vlookup_approx(value, lookup_array, result_array):
            matches = [i for i, x in enumerate(lookup_array) if x <= value]
            if matches:
                index = matches[-1]
                return result_array[index]
            else:
                return result_array[-1]  # Return the last value if no match is found

        # Generate the infill rows and get the updated drill data
        def generate_correct_infill_rows(max_infill=25):
            if drill_data is None:
                print("Error: drill_data is not loaded.")
                return None  # Early exit if drill_data is not loaded

            all_result_rows = []  # To hold all rows including infill rows

            unique_holes = drill_data[hole_id_col_drill].unique()

            for hole_id in unique_holes:
                drill_data_filtered = drill_data[drill_data[hole_id_col_drill] == hole_id]
                print(f"Number of rows for hole_id {hole_id}: {len(drill_data_filtered)}")

                start_depth = 0 if context.scene.collar_start_depth == 'None' else collar_data[collar_data[hole_id_col_collar] == hole_id][start_depth_collar].iloc[0]
                final_depth = collar_data[collar_data[hole_id_col_collar] == hole_id][final_depth_collar].iloc[0]
                
                collar_matches = collar_data[collar_data[hole_id_col_collar] == hole_id]
                print(f"Length of collar_matches for hole_id {hole_id}: {len(collar_matches)}")
                if not collar_matches.empty:
                    start_depth = 0 if context.scene.collar_start_depth == 'None' else collar_matches[start_depth_collar].iloc[0]
                    final_depth = collar_matches[final_depth_collar].iloc[0]
                else:
                    print(f"No collar data found for hole_id {hole_id}, skipping...")
                    continue

                last_to_m = start_depth

                for _, row in drill_data_filtered.iterrows():
                    from_depth_col = from_depth_col_drill
                    to_depth_col = to_depth_col_drill
                    

                    if row[from_depth_col] - last_to_m > 0:
                        infill_from = last_to_m
                        while infill_from < row[from_depth_col]:
                            infill_to = min(infill_from + max_infill, row[from_depth_col])
                            # Use the column names for keys in infill_row
                            infill_row = {hole_id_col_drill: hole_id, from_depth_col: infill_from, to_depth_col: infill_to}
                            for col in drill_data_filtered.columns:
                                if col not in [from_depth_col, to_depth_col, hole_id_col_drill]:
                                    infill_row[col] = None  # Set default value for other columns
                            all_result_rows.append(infill_row)
                            infill_from = infill_to

                    # Add the existing row with updated 'last_to_m' value
                    row_dict = row.to_dict()
                    row_dict[hole_id_col_drill] = hole_id
                    all_result_rows.append(row_dict)
                    last_to_m = row[to_depth_col]

                # Infill after the last depth 
                if last_to_m < final_depth:
                    print(f"Adding infill rows after the last recorded depth for hole_id {hole_id}")
                    infill_from = last_to_m
                    while infill_from < final_depth:
                        infill_to = min(infill_from + max_infill, final_depth)
                        # Correctly use the column names for keys in infill_row
                        infill_row = {hole_id_col_drill: hole_id, from_depth_col: infill_from, to_depth_col: infill_to}
                        for col in drill_data_filtered.columns:
                            if col not in [from_depth_col, to_depth_col, hole_id_col_drill]:
                                infill_row[col] = None  # Set default value for other columns
                        all_result_rows.append(infill_row)
                        infill_from = infill_to

            result_df = pd.DataFrame(all_result_rows)
            
            # Iterate over each unique hole ID to add a new row based on min from_depth
            for hole_id in unique_holes:
                hole_data = result_df[result_df[hole_id_col_drill] == hole_id]
                if hole_data.empty:
                    continue

                min_from_depth = hole_data[from_depth_col_drill].min()

                # Converting new_row to a DataFrame before appending
                new_row_df = pd.DataFrame([{
                    hole_id_col_drill: hole_id,
                    from_depth_col_drill: min_from_depth,
                    to_depth_col_drill: min_from_depth,
                    'x': np.nan, 'y': np.nan, 'z': np.nan
                }])
                
                result_df = pd.concat([result_df, new_row_df], ignore_index=True)

            result_df = result_df.sort_values(by=[hole_id_col_drill, to_depth_col_drill]).reset_index(drop=True)

            return result_df
        
        # Generate the infill rows and get the updated drill data
        result_df = generate_correct_infill_rows(max_infill=25) # set to 25 meter intervals

        if result_df is None:
            self.report({'WARNING'}, "Failed to generate infill rows!")
            return pd.DataFrame()
        
        drill_data = result_df

        drill_data['x'] = np.nan
        drill_data['y'] = np.nan
        drill_data['z'] = np.nan
        
        unique_holes = drill_data[hole_id_col_drill].unique()
        print(f"Found {len(unique_holes)} unique hole IDs: {unique_holes}")
        
        # Check for missing hole IDs in collar and survey data
        missing_in_collar = set(unique_holes) - set(collar_data[hole_id_col_collar].unique())
        missing_in_survey = set(unique_holes) - set(survey_data[hole_id_col_survey].unique())
        if missing_in_collar or missing_in_survey:
            missing_ids_message = "Missing hole IDs in collar data: {} and/or in survey data: {}.".format(
                ", ".join(missing_in_collar), ", ".join(missing_in_survey))
            self.report({'WARNING'}, missing_ids_message)
            return pd.DataFrame()
        
        try:
            for hole_id in unique_holes:
                # Filter collar, survey, and drill data by hole ID
                collar_data_filtered = collar_data[collar_data[hole_id_col_collar] == hole_id]
                survey_data_filtered = survey_data[survey_data[hole_id_col_survey] == hole_id]
                
                # Use result_df to filter drill data by hole_id
                drill_data_filtered = result_df[result_df[hole_id_col_drill] == hole_id]
                

                # Identify the minimum depth value for this hole
                min_depth = drill_data_filtered[to_depth_col_drill].min()

                # Initial coordinates for each hole
                prev_x = collar_data_filtered.iloc[0][easting_col_collar]
                prev_y = collar_data_filtered.iloc[0][northing_col_collar]
                prev_z = collar_data_filtered.iloc[0][elevation_col_collar]

                # Populate the row corresponding to the minimum depth value with collar coordinates
                idx_in_main_df = drill_data.index[(drill_data[hole_id_col_drill] == hole_id) & (drill_data[to_depth_col_drill] == min_depth)].tolist()[0]
                drill_data.at[idx_in_main_df, 'x'] = prev_x
                drill_data.at[idx_in_main_df, 'y'] = prev_y
                drill_data.at[idx_in_main_df, 'z'] = prev_z
            
                # Initialize coordinates
                prev_depth_F2 = min_depth
                # Loop through drill data for the current hole
                for index in range(len(drill_data_filtered)):
                    next_row = drill_data_filtered.iloc[index]  
                    depth_F3 = next_row[to_depth_col_drill]

                    # Get values for depth using the vlookup approximation
                    azimuth_F3 = vlookup_approx(depth_F3, survey_data_filtered[depth_col_survey].values, survey_data_filtered[azimuth_col_survey].values)
                    dip_F3 = vlookup_approx(depth_F3, survey_data_filtered[depth_col_survey].values, survey_data_filtered[dip_col_survey].values)

                    # Apply the calculation for x, y, z using the depth difference
                    delta_x = (depth_F3 - prev_depth_F2) * np.sin(np.radians(azimuth_F3)) * np.cos(np.radians(dip_F3))
                    delta_y = (depth_F3 - prev_depth_F2) * np.cos(np.radians(azimuth_F3)) * np.cos(np.radians(dip_F3))
                    delta_z = (depth_F3 - prev_depth_F2) * np.sin(np.radians(dip_F3))

                    # Cumulatively add the deltas to the previous coordinates
                    new_x = prev_x + delta_x
                    new_y = prev_y + delta_y
                    new_z = prev_z + delta_z

                    # Store these new values for the next iteration
                    prev_x, prev_y, prev_z = new_x, new_y, new_z
                    prev_depth_F2 = depth_F3  # Update depth for next iteration

                    # Update the original DataFrame with new x, y, and z values
                    idx_in_main_df = drill_data.index[(drill_data[hole_id_col_drill] == hole_id) & (drill_data[to_depth_col_drill] == depth_F3)].tolist()[0]
                    drill_data.at[idx_in_main_df, 'x'] = new_x
                    drill_data.at[idx_in_main_df, 'y'] = new_y
                    drill_data.at[idx_in_main_df, 'z'] = new_z

        except Exception as e:
            self.report({'WARNING'}, f"Failed to generate desurveyed data! Error: {str(e)}")
            return pd.DataFrame()

        return drill_data


class SaveCSVOperator(bpy.types.Operator):
    bl_idname = "desurvey.save_csv"
    bl_label = "Save Desurveyed CSV"

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        global drill_data

        if not drill_data.empty:
            file_path = bpy.path.ensure_ext(self.filepath, ".csv")
            drill_data.to_csv(file_path, index=False)
            self.report({'INFO'}, "Desurveyed data saved successfully!")
        else:
            self.report({'WARNING'}, "No desurveyed data to save!")

        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


def register():
    bpy.utils.register_class(ContinuousDesurveyCalcPanel)
    bpy.utils.register_class(UploadDrillDataOperator)
    bpy.utils.register_class(UploadSurveyDataOperator)
    bpy.utils.register_class(UploadCollarDataOperator)
    bpy.utils.register_class(GenerateCSVOperator)
    bpy.utils.register_class(SaveCSVOperator)

    bpy.types.Scene.drill_hole_id = bpy.props.EnumProperty(items=update_drill_columns)
    bpy.types.Scene.drill_from_depth = bpy.props.EnumProperty(items=update_drill_columns)
    bpy.types.Scene.drill_to_depth = bpy.props.EnumProperty(items=update_drill_columns)
    bpy.types.Scene.survey_hole_id = bpy.props.EnumProperty(items=update_survey_columns)
    bpy.types.Scene.survey_depth = bpy.props.EnumProperty(items=update_survey_columns)
    bpy.types.Scene.survey_azimuth = bpy.props.EnumProperty(items=update_survey_columns)
    bpy.types.Scene.survey_dip = bpy.props.EnumProperty(items=update_survey_columns)
    bpy.types.Scene.collar_hole_id = bpy.props.EnumProperty(items=update_collar_columns)
    bpy.types.Scene.collar_easting = bpy.props.EnumProperty(items=update_collar_columns)
    bpy.types.Scene.collar_northing = bpy.props.EnumProperty(items=update_collar_columns)
    bpy.types.Scene.collar_elevation = bpy.props.EnumProperty(items=update_collar_columns)
    bpy.types.Scene.collar_start_depth = bpy.props.EnumProperty(items=update_collar_columns)
    bpy.types.Scene.collar_final_depth = bpy.props.EnumProperty(items=update_collar_columns)
    bpy.types.Scene.drill_columns = bpy.props.StringProperty()
    bpy.types.Scene.survey_columns = bpy.props.StringProperty()
    bpy.types.Scene.collar_columns = bpy.props.StringProperty()


def unregister():
    bpy.utils.unregister_class(ContinuousDesurveyCalcPanel)
    bpy.utils.unregister_class(UploadDrillDataOperator)
    bpy.utils.unregister_class(UploadSurveyDataOperator)
    bpy.utils.unregister_class(UploadCollarDataOperator)
    bpy.utils.unregister_class(GenerateCSVOperator)
    bpy.utils.unregister_class(SaveCSVOperator)

    del bpy.types.Scene.drill_hole_id
    del bpy.types.Scene.drill_from_depth
    del bpy.types.Scene.drill_to_depth
    del bpy.types.Scene.survey_hole_id
    del bpy.types.Scene.survey_depth
    del bpy.types.Scene.survey_azimuth
    del bpy.types.Scene.survey_dip
    del bpy.types.Scene.collar_hole_id
    del bpy.types.Scene.collar_easting
    del bpy.types.Scene.collar_northing
    del bpy.types.Scene.collar_elevation
    del bpy.types.Scene.collar_start_depth
    del bpy.types.Scene.collar_final_depth
    del bpy.types.Scene.drill_columns
    del bpy.types.Scene.survey_columns
    del bpy.types.Scene.collar_columns


if __name__ == "__main__":
    register()
