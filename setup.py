import sys
import setuptools

# cx_freeze interferes with 'normal' setup, so only load it when the relevant
# cx_freeze functions are run
if sys.argv[1] in ("build_msi", "build_dmg", "build_app"):
    freezing = True
    from cx_Freeze import setup, Executable
else:
    freezing = False
    from setuptools import setup

# load some metadata from other files
with open("README.md", "r") as fh:
    long_description = fh.read()

with open("VERSION", "r") as fh:
    version = fh.read()

with open("requirements.txt", "r") as fh:
    requirements = [line.strip() for line in fh.readlines()]

# again, some extra cx_freeze stuff
extra_setup = {}
if freezing:
    base = None

    # GUI applications require a different base on Windows (the default is for a
    # console application).
    if sys.platform == "win32":
        base = "Win32GUI"

    # these excludes don't seem to do much unfortunately...
    assets = ["VERSION"]
    build_exe_options = {
        "optimize": 2,
        "packages": [req.split("==")[0] for req in requirements],
        "excludes": ["wx.lib",
                     "tkinter", "jinja2", "lib2to3", "numpy ", "pandas", "pip",
                     "matplotlib", "scipy", "unittest", "sqlite3", "distutils",
                     ],
        "include_files": [(asset, "lib/dmi_instascraper/" + asset) for asset in assets]
    }

    # fancy icon and nice exe name
    extra_setup = {
        "options": {"build_exe": build_exe_options},
        "executables": [Executable(
            "dmi_instascraper/__main__.py",
            base=base,
            targetName="dmi-instascraper.exe",
            icon="icon.ico"
        )]
    }

setup(
    name="dmi-instascraper",
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