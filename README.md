# **Reliance on BlenderGIS**

Please ensure you have BlenderGIS installed (awesome free add-on), as you will need this to set up a georeferenced scene in blender. Addtionally, you'll want it for other features including; 
- Import DEMs to create topography surface.
- Drape georeferenced images on topography.
- Import shapefiles, export as shapefiles.

Link to BlenderGIS: [BlenderGIS](https://github.com/domlysz/BlenderGIS)

# **Installation Instructions**

### **1. Download the .zip File**
- Download the `.zip` file from the **main branch** of the repository.
   - *(Click **Code** → **Download ZIP**)*

### **2. Install the Required Dependencies**

Dependencies must be installed in your Blender environment before installing the add-on, or an error message will appear during installation. **To view the console** (recommended) while running Blender Click **Window** → **Toggle System Console**.
  
- **Open Blender**:
   - Make sure if you are running windows to open blender with *****Run as Administrator***** for the depenency install. Once the install is completed once, there is no need to continue to run blender as an administrator or run the dependency install again.

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

---

### **3. Install the Add-on in Blender**

- Go to **Edit** → **Preferences**.
- In the Preferences window, navigate to the **Add-ons** tab.
- Click on **Install...** at the top of the window.
- In the file browser that appears, locate the `.zip` file you downloaded and select it.
- After installation, enable the add-on by checking the box next to **GeoModeller** in the list of installed add-ons.
   - *(If you are using Blender 4.2 or later, the add-on will automatically install without requiring you to check the box. Note; there is sometimes a delay between checking the box and completion of the add-on install)*
- Click 'n' on your keyboard to bring up the tool sidebar. Here you will see 'GeoModeller' tab. 
