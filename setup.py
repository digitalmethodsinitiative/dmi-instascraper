import sys
import setuptools

# cx_freeze interferes with 'normal' setup, so only load it when the relevant
# cx_freeze functions are run
if sys.argv[1] in ("bdist_msi", "bdist_mac", "bdist_dmg"):
    freezing = True
    from cx_Freeze import setup, Executable
else:
    freezing = False
    from setuptools import setup

# load some metadata from other files
with open("README.md", "r") as fh:
    long_description = fh.read()

with open("dmi_instascraper/VERSION", "r") as fh:
    version = fh.read()

with open("requirements.txt", "r") as fh:
    requirements = [line.strip() for line in fh.readlines()]

app_name = "dmi-instascraper"

# again, some extra cx_freeze stuff
extra_setup = {}
if freezing:
    base = None

    # GUI applications require a different base on Windows (the default is for a
    # console application).
    if sys.platform == "win32":
        base = "Win32GUI"
        exe_name = "dmi-instascraper.exe"
    else:
        exe_name = "DMInstascraper"
        app_name = exe_name

    # these excludes don't seem to do much unfortunately...
    assets = ["dmi_instascraper/VERSION"]
    build_exe_options = {
        "optimize": 2,
        "packages": ["wx", "instaloader", "requests"],
        "includes": ["queue"],
        "excludes": ["matplotlib.tests", "numpy.random._examples", "wx.lib", "jinja2"],
        "include_files": [(asset, "lib/dmi_instascraper/" + asset) for asset in assets]
    }

    # fancy icon and nice exe name
    extra_setup = {
        "options": {"build_exe": build_exe_options},
        "executables": [Executable(
            "dmi_instascraper/__main__.py",
            base=base,
            targetName=exe_name,
            icon="icon.ico"
        )]
    }

    if sys.platform == "darwin":
        extra_setup["options"]["bdist_mac"] = {
            "iconfile": "icon.icns",
            "bundle_name": "DMI Instagram Scraper",
        }

        extra_setup["options"]["bdist_dmg"]: {
            "volume_label": "DMI Instagram Scraper",
            "applications_shortcut": True
        }

setup(
    name=app_name,
    version=version,
    author="Digital Methods Initiative",
    author_email="stijn.peeters@uva.nl",
    description="A GUI wrapper around instaloader to scrape Instagram hashtags and users with",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/digitalmethodsinitiative/dmi-instascraper",
    packages=setuptools.find_packages(),
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    install_requires=requirements,
    **extra_setup
)
