import guzzle_sphinx_theme

project = "yq"
copyright = "Andrey Kislyuk"
author = "Andrey Kislyuk"
version = ""
release = ""
language = None
master_doc = "index"
extensions = ["sphinx.ext.autodoc", "sphinx.ext.viewcode"]
source_suffix = [".rst", ".md"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
pygments_style = "sphinx"
html_theme_path = guzzle_sphinx_theme.html_theme_path()
html_theme = "guzzle_sphinx_theme"
html_theme_options = {
    "project_nav_name": project,
    "projectlink": "https://github.com/kislyuk/" + project,
}
html_sidebars = {
    "**": [
        "logo-text.html",
        # "globaltoc.html",
        "localtoc.html",
        "searchbox.html"
    ]
}
