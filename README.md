# Python Scripts for OriginPro Automation

A collection of Python scripts using the `originpro` library to automate plotting, data management, and other routine tasks in OriginLab's Origin software. These tools are designed to streamline the workflow for scientific data analysis and visualization.

## Scripts Overview

This repository contains the following scripts:

* **`plot_active_sheet.py`**
    * Generates a quick 2D graph from the first two columns of the currently active worksheet in Origin.

* **`plot_multiple_workbooks.py`**
    * Plots data from multiple different workbooks into a single, combined graph. It allows users to select workbooks by providing a specific list or a numerical range of indices.

* **`plot_datafile_columns.py`**
    * Imports data from an external text file (e.g., `.txt`) and plots multiple specified columns from that file into a single, stylized scatter graph.

* **`create_worksheet_index.py`**
    * Scans the entire Origin project, finds all existing worksheets, and generates a new summary sheet that acts as a "Table of Contents" with the name and index of each worksheet.

## Requirements

* [OriginPro](https://www.originlab.com/) (with Python support enabled)
* Python 3.x
* `originpro` library
* `pandas` library

## Usage

1.  Ensure you have a running instance of OriginPro.
2.  Open the project file you wish to work with.
3.  Run the desired Python script from your terminal or IDE.

*Note: Some scripts may contain hardcoded file paths or column names. Please modify them as needed for your specific use case.*

## Author

* **Prathamesh Deshmukh**

Feel free to use, modify, and distribute these scripts. If you find them useful, a star on the repository would be appreciated!
