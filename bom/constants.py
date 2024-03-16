NO_CHOICE = ("", "-----")

SUBSCRIPTION_TYPE_FREE = "F"
SUBSCRIPTION_TYPE_PRO = "P"
SUBSCRIPTION_TYPES = (
    (SUBSCRIPTION_TYPE_FREE, "Free"),
    (SUBSCRIPTION_TYPE_PRO, "Pro"),
)

ROLE_TYPE_ADMIN = "A"
ROLE_TYPE_VIEWER = "V"
ROLE_TYPES = (
    (ROLE_TYPE_ADMIN, "Admin"),
    (ROLE_TYPE_VIEWER, "Viewer"),
)

CONFIGURATION_TYPE_RELEASED = "R"
CONFIGURATION_TYPE_WORKING = "W"
CONFIGURATION_TYPES = (
    (CONFIGURATION_TYPE_RELEASED, "غیر فعال"),
    (CONFIGURATION_TYPE_WORKING, "فعال"),
)

NUMBER_SCHEME_INTELLIGENT = "I"
NUMBER_SCHEME_SEMI_INTELLIGENT = "S"
NUMBER_SCHEMES = (
    (NUMBER_SCHEME_INTELLIGENT, "Intelligent"),
    (NUMBER_SCHEME_SEMI_INTELLIGENT, "Semi-Intelligent"),
)

NUMBER_CLASS_CODE_LEN_MIN = 2
NUMBER_CLASS_CODE_LEN_MAX = 16
NUMBER_CLASS_CODE_LEN_DEFAULT = 3
NUMBER_ITEM_LEN_MIN = 3
NUMBER_ITEM_LEN_MAX = 128
NUMBER_ITEM_LEN_DEFAULT = 4
NUMBER_VARIATION_LEN_MIN = 0
NUMBER_VARIATION_LEN_MAX = 16
NUMBER_VARIATION_LEN_DEFAULT = 2

DATA_SOURCE_OCTOPART = "octopart"
DATA_SOURCE_MOUSER = "mouser"
DATA_SOURCES = (
    NO_CHOICE,
    (DATA_SOURCE_OCTOPART, "octopart"),
    (DATA_SOURCE_MOUSER, "mouser"),
)

VALUE_UNITS = (
    NO_CHOICE,
    ("Ohms", "\u03a9"),
    ("mOhms", "m\u03a9"),
    ("kOhms", "k\u03a9"),
    ("MOhms", "M\u03a9"),
    ("F", "F"),
    ("pF", "pF"),
    ("nF", "nF"),
    ("uF", "\u03bcF"),
    ("V", "V"),
    ("uV", "\u03bcV"),
    ("mV", "mV"),
    ("A", "A"),
    ("uA", "\u03bcA"),
    ("mA", "mA"),
    ("C", "\u00b0C"),
    ("F", "\u00b0F"),
    ("H", "H"),
    ("nH", "nH"),
    ("mH", "mH"),
    ("uH", "\u03bcH"),
    ("Hz", "Hz"),
    ("kHz", "kHz"),
    ("MHz", "MHz"),
    ("GHz", "GHz"),
    ("Other", "Other"),
)

PACKAGE_TYPES = (
    NO_CHOICE,
    ("0201 smd", "0201 smd"),
    ("0402 smd", "0402 smd"),
    ("0603 smd", "0603 smd"),
    ("0805 smd", "0805 smd"),
    ("1206 smd", "1206 smd"),
    ("1210 smd", "1210 smd"),
    ("1812 smd", "1812 smd"),
    ("2010 smd", "2010 smd"),
    ("2512 smd", "2512 smd"),
    ("1/8 radial", "1/8 radial"),
    ("1/4 radial", "1/4 radial"),
    ("1/2 radial", "1/2 radial"),
    ("Size A", "Size A"),
    ("Size B", "Size B"),
    ("Size C", "Size C"),
    ("Size D", "Size D"),
    ("Size E", "Size E"),
    ("SOT-23", "SOT-23"),
    ("SOT-223", "SOT-233"),
    ("DIL", "DIL"),
    ("SOP", "SOP"),
    ("SOIC", "SOIC"),
    ("QFN", "QFN"),
    ("QFP", "QFP"),
    ("QFT", "QFT"),
    ("PLCC", "PLCC"),
    ("VGA", "VGA"),
    ("BGA", "BGA"),
    ("CSP", "CSP"),
    ("Other", "Other"),
)

MATERIAL_TYPES = (
    NO_CHOICE,
    ("with_loi", "با لحاظ کردن پرت (فریت)"),
    ("no_loi", "بدون در نظر گرفتن پرت (محصول غیر فریت)"),
    ("no_bom", "مواد اولیه (قیمت مشخص)"),
    ("Other", "سایر"),
)

DISTANCE_UNITS = (
    NO_CHOICE,
    ("mil", "mil"),
    ("in", "in"),
    ("ft", "ft"),
    ("yd", "yd"),
    ("km", "km"),
    ("m", "m"),
    ("cm", "cm"),
    ("mm", "mm"),
    ("um", "\u03bcm"),
    ("nm", "nm"),
    ("Other", "Other"),
)

WEIGHT_UNITS = (
    NO_CHOICE,
    ("mg", "mg"),
    ("g", "g"),
    ("kg", "kg"),
    ("oz", "oz"),
    ("lb", "lb"),
    ("Other", "Other"),
)

TEMPERATURE_UNITS = (
    NO_CHOICE,
    ("C", "\u00b0C"),
    ("F", "\u00b0F"),
    ("Other", "Other"),
)

WAVELENGTH_UNITS = (
    NO_CHOICE,
    ("km", "km"),
    ("m", "m"),
    ("cm", "cm"),
    ("mm", "mm"),
    ("um", "\u03bcm"),
    ("nm", "nm"),
    ("A", "\u212b"),
    ("Other", "Other"),
)

FREQUENCY_UNITS = (
    NO_CHOICE,
    ("Hz", "Hz"),
    ("kHz", "kHz"),
    ("MHz", "MHz"),
    ("GHz", "GHz"),
    ("Other", "Other"),
)

MEMORY_UNITS = (
    NO_CHOICE,
    ("KB", "KB"),
    ("MB", "MB"),
    ("GB", "GB"),
    ("TB", "TB"),
    ("Other", "Other"),
)

INTERFACE_TYPES = (
    NO_CHOICE,
    ("I2C", "I2C"),
    ("SPI", "SPI"),
    ("CAN", "CAN"),
    ("One-Wire", "1-Wire"),
    ("RS485", "RS-485"),
    ("RS232", "RS-232"),
    ("WiFi", "Wi-Fi"),
    ("4G", "4G"),
    ("BT", "Bluetooth"),
    ("BTLE", "Bluetooth LE"),
    ("Z_Wave", "Z-Wave"),
    ("Zigbee", "Zigbee"),
    ("LAN", "LAN"),
    ("USB", "USB"),
    ("HDMI", "HDMI"),
    ("Other", "Other"),
)

POWER_UNITS = (
    NO_CHOICE,
    ("W", "W"),
    ("uW", "\u03bcW"),
    ("mW", "mW"),
    ("kW", "kW"),
    ("MW", "MW"),
    ("Other", "Other"),
)

VOLTAGE_UNITS = (
    NO_CHOICE,
    ("V", "V"),
    ("uV", "\u03bcV"),
    ("mV", "mV"),
    ("kV", "kV"),
    ("MV", "MV"),
    ("Other", "Other"),
)

CURRENT_UNITS = (
    NO_CHOICE,
    ("A", "A"),
    ("uA", "\u03bcV"),
    ("mA", "mA"),
    ("kA", "kA"),
    ("MA", "MA"),
    ("Other", "Other"),
)

DEFAULT_SELLER_NAME = "انتخاب نشده (پیش فرض)"
