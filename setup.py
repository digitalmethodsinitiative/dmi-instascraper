import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

with open("VERSION", "r") as fh:
    version = fh.read()

with open("requirements.txt", "r") as fh:
    requirements = [line.strip() for line in fh.readlines()]

setuptools.setup(
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
        "License :: OSI Approved :: Apache License 2.0",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    install_requires=requirements
)