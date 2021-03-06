from setuptools import setup, find_packages

with open("readme.md", "r") as fh:
    long_description = fh.read()

setup(
    name="nucperiodpy",
    version="0.5",
    description='Analyze mutational periodicity about nucleosomes',
    long_description_content_type="text/markdown",
    url='https://github.com/bmorledge-hampton19/Nucleosome-Mutation-Analysis',
    author='Ben Morledge-Hampton',
    author_email='b.morledge-hampton@wsu.edu',
    license='MIT',
    python_requires='>=3.7',
    packages=find_packages(),
    package_data={"nucperiodpy": ["run_nucperiodR/*.r", "run_nucperiodR/*.R", "Tkinter_scripts/test_tube.png",
                  "input_parsing/default_BPDE_lesion_calling.tsv"]},
    entry_points=dict(
        console_scripts=['nucperiod=nucperiodpy.Main:main']
    ),
    
)