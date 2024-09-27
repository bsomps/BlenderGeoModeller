import subprocess
import sys
import os
from pathlib import Path
import pkg_resources

def is_package_installed(package):
    try:
        pkg_resources.get_distribution(package)
        return True
    except pkg_resources.DistributionNotFound:
        return False

def install_package(py_exec, lib_dir, package):
    if is_package_installed(package.split("==")[0]):
        print(f"{package} is already installed. Skipping...")
        return

    try:
        print(f"Installing {package}...")
        result = subprocess.run([py_exec, "-m", "pip", "install", f"--target={lib_dir}", package], check=True, capture_output=True, text=True)
        print(result.stdout)
        print(f"Successfully installed {package} to {lib_dir}.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to install {package}.")
        print(e.output)

def ensure_packages():
    # Get the path to blenders Python executable
    py_exec = sys.executable

    # Get the path to the lib directory
    lib_dir = os.path.join(Path(py_exec).parent.parent, 'lib', 'site-packages')

    # Print the directory where the packages will be installed
    print(f"Packages will be installed to: {lib_dir}")

    # Ensure pip 
    try:
        print("Ensuring pip is installed...")
        subprocess.run([py_exec, "-m", "ensurepip", "--user"], check=True, capture_output=True, text=True)
        print("pip is installed.")
    except subprocess.CalledProcessError as e:
        print("Failed to ensure pip is installed.")
        print(e.output)

    # Update pip 
    try:
        print("Updating pip...")
        subprocess.run([py_exec, "-m", "pip", "install", "--upgrade", "pip"], check=True, capture_output=True, text=True)
        print("pip is updated.")
    except subprocess.CalledProcessError as e:
        print("Failed to update pip.")
        print(e.output)

    # List of packages to install
    required_packages = {
        "numpy": "1.26.0",
        "scipy": "1.13.0",
        "matplotlib": "3.8.4",
        "gempy": "2024.1.4",
        "torch": "2.2.2",
        "torchvision": "0.17.2",
        "torchaudio": "2.2.2",
        "pandas": "2.2.2",
        "scikit-image": "0.23.2"
    }

    # Install each package
    for package, version in required_packages.items():
        install_package(py_exec, lib_dir, f"{package}=={version}")

    # Print success message
    print("\nAll dependencies installed successfully. You may now install the add-on to Blender.")

# Run the package installation process
ensure_packages()