"""Every chain this project knows how to read, grouped by the portal it uses.

The Israeli Price Transparency Law (חוק קידום התחרות בענף המזון) requires every
large chain to publish full price files for every branch. Each chain publishes
through one of a few portals. To add a chain on a supported portal, add a line
here; to add a portal, add a class to sources.py and a group here.
"""

CHAINS = [
    # Own portals.
    {"key": "shufersal", "name": "שופרסל", "portal": "shufersal"},
    {"key": "carrefour", "name": "קרפור", "portal": "carrefour"},
    # Cerberus (url.publishedprices.co.il): public username, empty password.
    {"key": "ramilevy", "name": "רמי לוי", "portal": "cerberus", "user": "RamiLevi"},
    {"key": "yohananof", "name": "יוחננוף", "portal": "cerberus", "user": "yohananof"},
    {"key": "osherad", "name": "אושר עד", "portal": "cerberus", "user": "osherad"},
    {"key": "keshet", "name": "קשת טעמים", "portal": "cerberus", "user": "Keshet"},
    {"key": "tivtaam", "name": "טיב טעם", "portal": "cerberus", "user": "TivTaam"},
    {"key": "doralon", "name": "דור אלון", "portal": "cerberus", "user": "doralon"},
    {"key": "stopmarket", "name": "סטופמרקט", "portal": "cerberus", "user": "Stop_Market"},
    {"key": "politzer", "name": "פוליצר", "portal": "cerberus", "user": "politzer"},
    {"key": "salachdabach", "name": "סאלח דבאח", "portal": "cerberus", "user": "SalachD"},
    {"key": "freshmarket", "name": "פרש מרקט", "portal": "cerberus", "user": "freshmarket"},
    # Bina Projects (<prefix>.binaprojects.com).
    {"key": "shukhair", "name": "שוק העיר", "portal": "bina", "prefix": "shuk-hayir", "chain_id": "7290058148776"},
    {"key": "supersapir", "name": "סופר ספיר", "portal": "bina", "prefix": "supersapir", "chain_id": "7290058156016"},
    {"key": "goodpharm", "name": "גוד פארם", "portal": "bina", "prefix": "goodpharm", "chain_id": "7290058197699"},
    {"key": "kingstore", "name": "קינג סטור", "portal": "bina", "prefix": "kingstore", "chain_id": "7290058108879"},
    {"key": "zolvebegadol", "name": "זול ובגדול", "portal": "bina", "prefix": "zolvebegadol", "chain_id": "7290058173198"},
    {"key": "maayan2000", "name": "מעיין 2000", "portal": "bina", "prefix": "maayan2000", "chain_id": "7290058159628"},
]

BY_KEY = {c["key"]: c for c in CHAINS}


def source_for(chain):
    from . import sources
    cls = {"shufersal": sources.Shufersal, "carrefour": sources.Carrefour,
           "cerberus": sources.Cerberus, "bina": sources.Bina}[chain["portal"]]
    return cls(chain)
