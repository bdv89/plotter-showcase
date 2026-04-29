from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT
from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
                           QLabel, QFontComboBox, QSpinBox, QComboBox, QDoubleSpinBox,
                           QScrollArea, QWidget, QPushButton, QLineEdit, QCheckBox)

class CustomNavigationToolbar(NavigationToolbar2QT):
    """Custom Navigation Toolbar to remove specific buttons"""
    # Only include the desired toolitems
    toolitems = [t for t in NavigationToolbar2QT.toolitems if
                 t[0] not in ('Subplots', 'Customize')]

def create_group_box(title, layout=None):
    """Create a QGroupBox with optional layout"""
    group = QGroupBox(title)
    if layout:
        group.setLayout(layout)
    return group

def create_form_layout():
    """Create a new form layout"""
    return QFormLayout()

def create_scroll_area(widget):
    """Create a scroll area containing the widget"""
    scroll = QScrollArea()
    scroll.setWidget(widget)
    scroll.setWidgetResizable(True)
    return scroll

def add_form_row(form_layout, label, widget):
    """Add a row to a form layout"""
    form_layout.addRow(label, widget)

def create_spin_box(minimum, maximum, value=None, step=1, decimals=0, special_value_text=None):
    """Create a spin box with given parameters"""
    if decimals > 0:
        spin = QDoubleSpinBox()
    else:
        spin = QSpinBox()
    
    spin.setRange(minimum, maximum)
    if value is not None:
        spin.setValue(value)
    spin.setSingleStep(step)
    
    if decimals > 0:
        spin.setDecimals(decimals)
        
    if special_value_text:
        spin.setSpecialValueText(special_value_text)
        
    return spin

def create_combo_box(items=None):
    """Create a combo box with optional items"""
    combo = QComboBox()
    if items:
        combo.addItems(items)
    return combo

def create_font_combo_box():
    """Create a font selection combo box"""
    return QFontComboBox()

def create_labeled_widget(label_text, widget):
    """Create a horizontal layout with a label and widget"""
    layout = QHBoxLayout()
    layout.addWidget(QLabel(label_text))
    layout.addWidget(widget)
    return layout

def create_button_row(*buttons):
    """Create a horizontal layout with buttons"""
    layout = QHBoxLayout()
    for button in buttons:
        if isinstance(button, str):
            btn = QPushButton(button)
        else:
            btn = button
        layout.addWidget(btn)
    return layout

def create_checkbox(text, checked=False):
    """Create a checkbox with text"""
    checkbox = QCheckBox(text)
    checkbox.setChecked(checked)
    return checkbox

def create_line_edit(text=""):
    """Create a line edit with optional text"""
    line_edit = QLineEdit()
    line_edit.setText(text)
    return line_edit

def create_vertical_layout(*widgets):
    """Create a vertical layout with widgets"""
    layout = QVBoxLayout()
    for widget in widgets:
        if isinstance(widget, (QVBoxLayout, QHBoxLayout, QFormLayout)):
            layout.addLayout(widget)
        else:
            layout.addWidget(widget)
    return layout

def create_horizontal_layout(*widgets):
    """Create a horizontal layout with widgets"""
    layout = QHBoxLayout()
    for widget in widgets:
        if isinstance(widget, (QVBoxLayout, QHBoxLayout, QFormLayout)):
            layout.addLayout(widget)
        else:
            layout.addWidget(widget)
    return layout

# Grid style mapping (backend code -> UI label)
GRID_STYLE_MAP = {
    '-': 'Solid -',
    '--': 'Dashed --',
    '-.': 'Dash-dot -.',
    ':': 'Dotted :'
}

# Reverse mapping (UI label -> backend code)
GRID_STYLE_REVERSE_MAP = {v: k for k, v in GRID_STYLE_MAP.items()}

# Legend location mapping
LEGEND_LOCATIONS = [
    ("Auto", "best"),
    ("Upper Right", "upper right"),
    ("Upper Left", "upper left"),
    ("Lower Left", "lower left"),
    ("Lower Right", "lower right"),
    ("Right", "right"),
    ("Center Left", "center left"),
    ("Center Right", "center right"),
    ("Lower Center", "lower center"),
    ("Upper Center", "upper center"),
    ("Center", "center"),
    ("Outside Right", "outside_right"),
    ("Outside Left", "outside_left"),
    ("Outside Top", "outside_top"),
    ("Outside Bottom", "outside_bottom"),
    ("Below Title", "below_title"),
    ("Below X-Axis", "below_xaxis")
]

# Scale types
SCALE_TYPES = ['linear', 'log', 'symlog', 'logit']