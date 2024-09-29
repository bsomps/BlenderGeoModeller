# **Reliance on BlenderGIS**

Please ensure you have BlenderGIS installed (awesome free add-on), as you will need this to set up a georeferenced scene in blender. Addtionally, you'll want it for other features including; 
- Import DEMs to create topography surface.
- Drape georeferenced images on topography.
- Import shapefiles, export as shapefiles.

Link to BlenderGIS download: [BlenderGIS](https://github.com/domlysz/BlenderGIS)

# **Installation Instructions**

### **1. Download the .zip File**
- Download the `.zip` file from the **main branch** of the repository.
   - *(Click **Code** → **Download ZIP**)*

### **2. Install the Required Dependencies**

Dependencies must be installed in your Blender environment before installing the add-on, or an error message will appear during installation. 
  
- **Open Blender**:
   - Make sure if you are running windows to open blender with *****Run as Administrator***** for the depenency install. Once the install is completed once, there is no need to continue to run blender as an administrator or run the dependency install again.
   - **To view the console** (recommended) while running Blender Click **Window** → **Toggle System Console**.

- **Navigate to the Text Editor**:
   - Change the editor type by clicking the small hierarchy tree button (top-left corner) in the **Outliner**, and select **Text Editor**, OR
   - Switch to the **Scripting** tab at the top of Blender.

- **Set up the Text Editor**:
   - Click **New** to add a new text block.
   - Either:
     - Copy and paste the contents of the `dependency_imports.py` script into the text editor, OR
     - Add the `dependency_imports.py` file by clicking **Add** (located in the Text Editor).

- **Run the Script**:
   - Click **Text** → **Run Script** to execute the dependency installer.

- **Monitor the Installation Progress**:
   - Track the installation progress in the **Console** window.
   - When the installation is complete, the console will display the message:
     - `"All dependencies installed successfully. You may now install the add-on to Blender."`

- **Note**: Depending on your system setup, the installation process may take **up to 10 minutes**.


### **3. Install the Add-on in Blender**

- Go to **Edit** → **Preferences**.
- In the Preferences window, navigate to the **Add-ons** tab.
- Click on **Install...** at the top of the window.
- In the file browser that appears, locate the `.zip` file you downloaded and select it.
- After installation, enable the add-on by checking the box next to **GeoModeller** in the list of installed add-ons.
   - *(If you are using Blender 4.2 or later, the add-on will automatically install without requiring you to check the box. Note; there is sometimes a delay between checking the box and completion of the add-on install)*
- Click 'n' on your keyboard to bring up the tool sidebar. Here you will see 'GeoModeller' tab.

---
![Alt text](https://github.com/bsomps/BlenderGeoModeller/blob/media/drillholevid.gif)


# **Overview Of Operators**

### **Drilling**
- **Desurvey Data**:
   - Upload survey, collar, and datasheet as **CSV files**. Fill in the drop-downs as appropriate.
   - Returns the uploaded datasheet with added x, y, z (easting, northing, elevation (m)) values for each row. Adds a new row for each collar coordinate. Save to your files.
   
- **Import Drill Holes (xyz)**:
   - Click 'Load CSV' to bring up the file browser and upload the desurveyed file. Fill in drop-downs as appropriate.
   - Returns 3 collections: Drill hole data (curve objects), drill hole traces (curve objects), and hole IDs (mesh objects).
   - Each curve object in the drill hole corresponds to a row in the CSV file, with the column values imported as custom properties for each object.
   
- **Manage Drill Holes**:
   - Stylize numerical or categorical data by selecting the collection that holds the drill hole data and then selecting the attribute you want to plot from the drop-down (populated based on the custom properties). Choose a desired color ramp. The color ramp options will automatically adjust based on whether your property is numerical or categorical. The color ramps are standard scientific matplotlib color ramps.
   - Option to adjust the color mapping for numerical properties based on the interquartile range (IQR) and user-defined scaling factor.
   - Option to dynamically size the curve objects for numerical properties along a log scale or linear scale.
   - Option to generate a legend (Note: You will need to switch your 'editor type' from 'Outliner' to 'Image Editor' in order to generate the legend).  
   
- **Drill Data Query**:
   - Hides objects based on query inputs.
   - For numerical properties, every value outside a defined range will be hidden.
   - For categorical columns, check the boxes for the properties you want to show; all remaining are hidden. 

- **Drill Hole Planner**:
   - Upload a CSV with planned hole IDs, azimuth, dip, planned depth (m), and your collar's x, y, and z.
   - Returns curve objects representing the planned drill holes in their correct spatial location and orientation.
   - Option to take manually created curve objects in your scene (make sure to create curves as 'Path') and then create a CSV output from these objects (ensure they are all in the same collection).

### **Point Data**
- **Import Point Data (xyz)**:
   - Click 'Load CSV' to bring up the file browser and upload the point data file. Fill in drop-downs as appropriate.
   - Returns points as sphere objects

- **Manage Point Data**:
   - Adjust colormapping and size
   - Same additional fucntionality as drill hole curve objects

- **Point Data Query**:
   - Same functionality as drill hole data query
  
### **Geological Modelling**
- **GemPy Modeller**:
   - Emulates the workflow of the gemPy module. (set extents, feed formation and orientation data, create structral frame)
   - Returns the interplated surfaces only
   - Complex models will have long processing times
