# -*- coding: utf-8 -*-
#
# core-admin documentation build configuration file, created by
# sphinx-quickstart on Thu Nov 13 15:02:15 2014.
#
# This file is execfile()d with the current directory set to its containing dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out
# serve to show the default.

import os
import subprocess
import sys
import time

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
sys.path.insert(0, os.path.abspath('../'))

# -- General configuration -----------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be extensions
# coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.coverage',
    'sphinx.ext.doctest',
    'sphinx.ext.intersphinx',
    'sphinx.ext.todo',
    'sphinx.ext.viewcode',

    'qubes.dochelpers',
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The encoding of source files.
source_encoding = 'utf-8'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = u'core-admin'
copyright = u'2010-{}, Invisible Things Lab'.format(time.strftime('%Y'))

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = open('../version').read().strip()
# The full version, including alpha/beta/rc tags.
release = subprocess.check_output(['git', 'describe', '--long', '--dirty']).strip()

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#language = None

# There are two options for replacing |today|: either, you set today to some
# non-false value, then it is used:
#today = ''
# Else, today_fmt is used as the format for a strftime call.
today_fmt = '%d.%m.%Y'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ['_build']

# The reST default role (used for this markup: `text`) to use for all documents.
#default_role = None

# If true, '()' will be appended to :func: etc. cross-reference text.
add_function_parentheses = True

# If true, the current module name will be prepended to all description
# unit titles (such as .. function::).
#add_module_names = True

# If true, sectionauthor and moduleauthor directives will be shown in the
# output. They are ignored by default.
#show_authors = False

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# A list of ignored prefixes for module index sorting.
#modindex_common_prefix = []

autodoc_member_order = 'groupwise'

# -- Options for HTML output ---------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#html_theme = 'default'
html_theme = 'nature'

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
html_theme_options = {
#   'collapsiblesidebar': True,
}

# Add any paths that contain custom themes here, relative to this directory.
#html_theme_path = []

# The name for this set of Sphinx documents.  If None, it defaults to
# "<project> v<release> documentation".
#html_title = None

# A shorter title for the navigation bar.  Default is the same as html_title.
#html_short_title = None

# The name of an image file (relative to this directory) to place at the top
# of the sidebar.
#html_logo = None

# The name of an image file (within the static path) to use as favicon of the
# docs.  This file should be a Windows icon file (.ico) being 16x16 or 32x32
# pixels large.
#html_favicon = None

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# If not '', a 'Last updated on:' timestamp is inserted at every page bottom,
# using the given strftime format.
html_last_updated_fmt = '%d.%m.%Y'

# If true, SmartyPants will be used to convert quotes and dashes to
# typographically correct entities.
#html_use_smartypants = True

# Custom sidebar templates, maps document names to template names.
#html_sidebars = {}

# Additional templates that should be rendered to pages, maps page names to
# template names.
#html_additional_pages = {}

# If false, no module index is generated.
#html_domain_indices = True

# If false, no index is generated.
#html_use_index = True

# If true, the index is split into individual pages for each letter.
#html_split_index = False

# If true, links to the reST sources are added to the pages.
#html_show_sourcelink = True

# If true, "Created using Sphinx" is shown in the HTML footer. Default is True.
#html_show_sphinx = True

# If true, "(C) Copyright ..." is shown in the HTML footer. Default is True.
#html_show_copyright = True

# If true, an OpenSearch description file will be output, and all pages will
# contain a <link> tag referring to it.  The value of this option must be the
# base URL from which the finished HTML is served.
#html_use_opensearch = ''

# This is the file name suffix for HTML files (e.g. ".xhtml").
#html_file_suffix = None

# Output file base name for HTML help builder.
htmlhelp_basename = 'core-admin-doc'


# -- Options for LaTeX output --------------------------------------------------

latex_elements = {
# The paper size ('letterpaper' or 'a4paper').
#'papersize': 'letterpaper',

# The font size ('10pt', '11pt' or '12pt').
#'pointsize': '10pt',

# Additional stuff for the LaTeX preamble.
#'preamble': '',
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass [howto/manual]).
latex_documents = [
  ('index', 'core-admin.tex', u'core-admin Documentation',
   u'Invisible Things Lab', 'manual'),
]

# The name of an image file (relative to this directory) to place at the top of
# the title page.
#latex_logo = None

# For "manual" documents, if this is true, then toplevel headings are parts,
# not chapters.
#latex_use_parts = False

# If true, show page references after internal links.
#latex_show_pagerefs = False

# If true, show URL addresses after external links.
#latex_show_urls = False

# Documents to append as an appendix to all manuals.
#latex_appendices = []

# If false, no module index is generated.
#latex_domain_indices = True


# -- Options for manual page output --------------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).

# authors should be empty and authors should be specified in each man page,
# because html builder will omit them
_man_pages_author = []

man_pages = [
    ('qvm-tools/qvm-add-appvm', 'qvm-add-appvm',
        u'Add an already installed appvm to the Qubes DB', _man_pages_author, 1),
    ('qvm-tools/qvm-add-template', 'qvm-add-template',
        u'Adds an already installed template to the Qubes DB', _man_pages_author, 1),
    ('qvm-tools/qvm-backup-restore', 'qvm-backup-restore',
        u'Restores Qubes VMs from backup', _man_pages_author, 1),
    ('qvm-tools/qvm-backup', 'qvm-backup',
        u'Create backup of specified VMs', _man_pages_author, 1),
    ('qvm-tools/qvm-block', 'qvm-block',
        u'List/set VM block devices.', _man_pages_author, 1),
    ('qvm-tools/qvm-clone-template', 'qvm-clone-template',
        u'Clones an existing template by copying all its disk files', _man_pages_author, 1),
    ('qvm-tools/qvm-clone', 'qvm-clone',
        u'Clones an existing VM by copying all its disk files', _man_pages_author, 1),
    ('qvm-tools/qvm-create-default-dvm', 'qvm-create-default-dvm',
        u'Creates a default disposable VM', _man_pages_author, 1),
    ('qvm-tools/qvm-create', 'qvm-create',
        u'Creates a new VM', _man_pages_author, 1),
    ('qvm-tools/qvm-firewall', 'qvm-firewall',
        u'Qubes firewall configuration', _man_pages_author, 1),
    ('qvm-tools/qvm-grow-private', 'qvm-grow-private',
        u'Increase private storage capacity of a specified VM', _man_pages_author, 1),
    ('qvm-tools/qvm-kill', 'qvm-kill',
        u'Kill the specified VM', _man_pages_author, 1),
    ('qvm-tools/qvm-ls', 'qvm-ls',
        u'List VMs and various information about them', _man_pages_author, 1),
    ('qvm-tools/qvm-pci', 'qvm-pci',
        u'List/set VM PCI devices', _man_pages_author, 1),
    ('qvm-tools/qvm-prefs', 'qvm-prefs',
        u'List/set various per-VM properties', _man_pages_author, 1),
    ('qvm-tools/qvm-remove', 'qvm-remove',
        u'Remove a VM', _man_pages_author, 1),
    ('qvm-tools/qvm-revert-template-changes', 'qvm-revert-template-changes',
        u'Revert changes to a template', _man_pages_author, 1),
    ('qvm-tools/qvm-run', 'qvm-run',
        u'Run a command on a specified VM', _man_pages_author, 1),
    ('qvm-tools/qvm-service', 'qvm-service',
        u'Manage (Qubes-specific) services started in VM', _man_pages_author, 1),
    ('qvm-tools/qvm-shutdown', 'qvm-shutdown',
        u'Gracefully shut down a VM', _man_pages_author, 1),
    ('qvm-tools/qvm-start', 'qvm-start',
        u'Start a specified VM', _man_pages_author, 1),
    ('qvm-tools/qvm-template-commit', 'qvm-template-commit',
        u'Commit changes to a template', _man_pages_author, 1),


    ('qubes-tools/qubes-guid', 'qubes-guid',
        u'Daemon for Qubes GUI isolation protocol', _man_pages_author, 1),
    ('qubes-tools/qubes-prefs', 'qubes-prefs',
        u'Display system-wide Qubes settings', _man_pages_author, 1),
]

if os.path.exists('sandbox.rst'):
    man_pages.append(('sandbox', 'sandbox',
        u'Sandbox manpage', 'Sandbox Author', 1))

# If true, show URL addresses after external links.
#man_show_urls = False


# -- Options for Texinfo output ------------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
  ('index', 'core-admin', u'core-admin Documentation',
   u'Invisible Things Lab', 'core-admin', 'One line description of project.',
   'Miscellaneous'),
]

# Documents to append as an appendix to all manuals.
#texinfo_appendices = []

# If false, no module index is generated.
#texinfo_domain_indices = True

# How to display URL addresses: 'footnote', 'no', or 'inline'.
#texinfo_show_urls = 'footnote'


# Example configuration for intersphinx: refer to the Python standard library.
intersphinx_mapping = {
    'python': ('http://docs.python.org/', None)}