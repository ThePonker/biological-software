"""
Vice County Short Names Mapping
================================
Complete mapping of all 157+ British and Irish Vice Counties to abbreviated names.

Usage:
    from vc_shortnames import VC_SHORT_NAMES
    
    short = VC_SHORT_NAMES.get('17', 'Surrey')  # Returns 'Surrey'
    short = VC_SHORT_NAMES.get('24', 'Buckinghamshire')  # Returns 'Bucks'
"""

# Vice County short names mapping
# Key: VC number as string (to match database format)
# Value: Short display name

VC_SHORT_NAMES = {
    # =========================================================================
    # ENGLAND (VC 1-71)
    # =========================================================================
    
    # South-West England
    "1": "W Cornwall",
    "2": "E Cornwall",
    "3": "S Devon",
    "4": "N Devon",
    "5": "S Somerset",
    "6": "N Somerset",
    "7": "N Wilts",
    "8": "S Wilts",
    "9": "Dorset",
    "10": "IoW",
    
    # South-East England
    "11": "S Hants",
    "12": "N Hants",
    "13": "W Sussex",
    "14": "E Sussex",
    "15": "E Kent",
    "16": "W Kent",
    "17": "Surrey",
    "18": "S Essex",
    "19": "N Essex",
    "20": "Herts",
    "21": "Middx",
    "22": "Berks",
    "23": "Oxon",
    "24": "Bucks",
    
    # East Anglia
    "25": "E Suffolk",
    "26": "W Suffolk",
    "27": "E Norfolk",
    "28": "W Norfolk",
    "29": "Cambs",
    "30": "Beds",
    "31": "Hunts",
    "32": "Northants",
    
    # West Midlands
    "33": "E Gloucs",
    "34": "W Gloucs",
    "36": "Herefs",
    "37": "Worcs",
    "38": "Warks",
    "39": "Staffs",
    "40": "Salop",
    
    # East Midlands & Lincolnshire
    "53": "S Lincs",
    "54": "N Lincs",
    "55": "Leics",
    "56": "Notts",
    "57": "Derbys",
    
    # North-West England
    "58": "Cheshire",
    "59": "S Lancs",
    "60": "W Lancs",
    "69": "Westmorland",
    "70": "Cumberland",
    
    # Yorkshire
    "61": "SE Yorks",
    "62": "NE Yorks",
    "63": "SW Yorks",
    "64": "MW Yorks",
    "65": "NW Yorks",
    
    # North-East England
    "66": "Durham",
    "67": "S Northumb",
    "68": "N Northumb",
    
    # Isle of Man
    "71": "IoM",
    
    # =========================================================================
    # WALES (VC 35, 41-52)
    # =========================================================================
    "35": "Monmouth",
    "41": "Glamorgan",
    "42": "Brecon",
    "43": "Radnor",
    "44": "Carms",
    "45": "Pembs",
    "46": "Cardigan",
    "47": "Montg",
    "48": "Merioneth",
    "49": "Caerns",
    "50": "Denbigh",
    "51": "Flint",
    "52": "Anglesey",
    
    # =========================================================================
    # SCOTLAND (VC 72-112)
    # =========================================================================
    
    # Borders & Southern Scotland
    "72": "Dumfries",
    "73": "Kirkcud",
    "74": "Wigtown",
    "75": "Ayrshire",
    "76": "Renfrew",
    "77": "Lanark",
    "78": "Peebles",
    "79": "Selkirk",
    "80": "Roxburgh",
    "81": "Berwick",
    "82": "E Lothian",
    "83": "Midlothian",
    "84": "W Lothian",
    
    # Central Scotland
    "85": "Fife",
    "86": "Stirling",
    "87": "W Perth",
    "88": "Mid Perth",
    "89": "E Perth",
    "90": "Angus",
    "91": "Kincardine",
    "92": "S Aberdeen",
    "93": "N Aberdeen",
    "94": "Banff",
    "95": "Moray",
    "96": "E Inverness",
    
    # Western Scotland
    "97": "W Inverness",
    "98": "Argyll Main",
    "99": "Dunbarton",
    "100": "Clyde Isles",
    "101": "Kintyre",
    "102": "S Ebudes",
    "103": "Mid Ebudes",
    "104": "N Ebudes",
    
    # Northern Scotland
    "105": "W Ross",
    "106": "E Ross",
    "107": "E Sutherland",
    "108": "W Sutherland",
    "109": "Caithness",
    "110": "Outer Heb",
    "111": "Orkney",
    "112": "Shetland",
    
    # Channel Islands
    "113": "Channel Is",
    
    # =========================================================================
    # IRELAND (VC H1-H40)
    # =========================================================================
    
    # South Ireland
    "H1": "S Kerry",
    "H2": "N Kerry",
    "H3": "W Cork",
    "H4": "Mid Cork",
    "H5": "E Cork",
    "H6": "Waterford",
    "H7": "S Tipperary",
    "H8": "Limerick",
    "H9": "Clare",
    "H10": "N Tipperary",
    "H11": "Kilkenny",
    "H12": "Wexford",
    "H13": "Carlow",
    "H14": "Laois",
    "H15": "SE Galway",
    "H16": "W Galway",
    "H17": "NE Galway",
    
    # Central Ireland
    "H18": "Offaly",
    "H19": "Kildare",
    "H20": "Wicklow",
    "H21": "Dublin",
    "H22": "Meath",
    "H23": "Westmeath",
    "H24": "Longford",
    "H25": "Roscommon",
    "H26": "E Mayo",
    "H27": "W Mayo",
    
    # North Ireland
    "H28": "Sligo",
    "H29": "Leitrim",
    "H30": "Cavan",
    "H31": "Louth",
    "H32": "Monaghan",
    "H33": "Fermanagh",
    "H34": "E Donegal",
    "H35": "W Donegal",
    "H36": "Tyrone",
    "H37": "Armagh",
    "H38": "Down",
    "H39": "Antrim",
    "H40": "Derry",
}


# Full names for reference (useful for tooltips)
VC_FULL_NAMES = {
    # England
    "1": "West Cornwall with Scilly",
    "2": "East Cornwall",
    "3": "South Devon",
    "4": "North Devon",
    "5": "South Somerset",
    "6": "North Somerset",
    "7": "North Wiltshire",
    "8": "South Wiltshire",
    "9": "Dorset",
    "10": "Isle of Wight",
    "11": "South Hampshire",
    "12": "North Hampshire",
    "13": "West Sussex",
    "14": "East Sussex",
    "15": "East Kent",
    "16": "West Kent",
    "17": "Surrey",
    "18": "South Essex",
    "19": "North Essex",
    "20": "Hertfordshire",
    "21": "Middlesex",
    "22": "Berkshire",
    "23": "Oxfordshire",
    "24": "Buckinghamshire",
    "25": "East Suffolk",
    "26": "West Suffolk",
    "27": "East Norfolk",
    "28": "West Norfolk",
    "29": "Cambridgeshire",
    "30": "Bedfordshire",
    "31": "Huntingdonshire",
    "32": "Northamptonshire",
    "33": "East Gloucestershire",
    "34": "West Gloucestershire",
    "35": "Monmouthshire",
    "36": "Herefordshire",
    "37": "Worcestershire",
    "38": "Warwickshire",
    "39": "Staffordshire",
    "40": "Shropshire",
    "41": "Glamorgan",
    "42": "Breconshire",
    "43": "Radnorshire",
    "44": "Carmarthenshire",
    "45": "Pembrokeshire",
    "46": "Cardiganshire",
    "47": "Montgomeryshire",
    "48": "Merionethshire",
    "49": "Caernarvonshire",
    "50": "Denbighshire",
    "51": "Flintshire",
    "52": "Anglesey",
    "53": "South Lincolnshire",
    "54": "North Lincolnshire",
    "55": "Leicestershire with Rutland",
    "56": "Nottinghamshire",
    "57": "Derbyshire",
    "58": "Cheshire",
    "59": "South Lancashire",
    "60": "West Lancashire",
    "61": "South-east Yorkshire",
    "62": "North-east Yorkshire",
    "63": "South-west Yorkshire",
    "64": "Mid-west Yorkshire",
    "65": "North-west Yorkshire",
    "66": "County Durham",
    "67": "South Northumberland",
    "68": "North Northumberland (Cheviotland)",
    "69": "Westmorland with North Lancashire",
    "70": "Cumberland",
    "71": "Isle of Man",
    
    # Scotland
    "72": "Dumfriesshire",
    "73": "Kirkcudbrightshire",
    "74": "Wigtownshire",
    "75": "Ayrshire",
    "76": "Renfrewshire",
    "77": "Lanarkshire",
    "78": "Peeblesshire",
    "79": "Selkirkshire",
    "80": "Roxburghshire",
    "81": "Berwickshire",
    "82": "East Lothian",
    "83": "Midlothian",
    "84": "West Lothian",
    "85": "Fife with Kinross",
    "86": "Stirlingshire",
    "87": "West Perthshire with Clackmannan",
    "88": "Mid Perthshire",
    "89": "East Perthshire",
    "90": "Angus (Forfarshire)",
    "91": "Kincardineshire",
    "92": "South Aberdeenshire",
    "93": "North Aberdeenshire",
    "94": "Banffshire",
    "95": "Moray (Elginshire)",
    "96": "East Inverness-shire with Nairn",
    "97": "West Inverness-shire",
    "98": "Argyll Main",
    "99": "Dunbartonshire",
    "100": "Clyde Isles",
    "101": "Kintyre",
    "102": "South Ebudes (Islay, Jura, Colonsay)",
    "103": "Mid Ebudes (Mull, Coll, Tiree)",
    "104": "North Ebudes (Skye, Rhum, etc.)",
    "105": "West Ross",
    "106": "East Ross",
    "107": "East Sutherland",
    "108": "West Sutherland",
    "109": "Caithness",
    "110": "Outer Hebrides",
    "111": "Orkney",
    "112": "Shetland",
    "113": "Channel Islands",
    
    # Ireland
    "H1": "South Kerry",
    "H2": "North Kerry",
    "H3": "West Cork",
    "H4": "Mid Cork",
    "H5": "East Cork",
    "H6": "Waterford",
    "H7": "South Tipperary",
    "H8": "Limerick",
    "H9": "Clare",
    "H10": "North Tipperary",
    "H11": "Kilkenny",
    "H12": "Wexford",
    "H13": "Carlow",
    "H14": "Laois (Queen's County)",
    "H15": "South-east Galway",
    "H16": "West Galway",
    "H17": "North-east Galway",
    "H18": "Offaly (King's County)",
    "H19": "Kildare",
    "H20": "Wicklow",
    "H21": "Dublin",
    "H22": "Meath",
    "H23": "Westmeath",
    "H24": "Longford",
    "H25": "Roscommon",
    "H26": "East Mayo",
    "H27": "West Mayo",
    "H28": "Sligo",
    "H29": "Leitrim",
    "H30": "Cavan",
    "H31": "Louth",
    "H32": "Monaghan",
    "H33": "Fermanagh",
    "H34": "East Donegal",
    "H35": "West Donegal",
    "H36": "Tyrone",
    "H37": "Armagh",
    "H38": "Down",
    "H39": "Antrim",
    "H40": "Londonderry",
}


def get_short_name(vc_code: str) -> str:
    """Get short name for a vice county code."""
    return VC_SHORT_NAMES.get(str(vc_code), str(vc_code))


def get_full_name(vc_code: str) -> str:
    """Get full name for a vice county code."""
    return VC_FULL_NAMES.get(str(vc_code), str(vc_code))


def get_display_name(vc_code: str, include_number: bool = True) -> str:
    """Get display name for dropdown: '17 - Surrey' or just 'Surrey'."""
    short = get_short_name(vc_code)
    if include_number:
        return f"{vc_code} - {short}"
    return short


# Region groupings for filtering
VC_REGIONS = {
    "england": [str(i) for i in range(1, 72) if i not in range(41, 53)] + ["35"],
    "wales": ["35"] + [str(i) for i in range(41, 53)],
    "scotland": [str(i) for i in range(72, 113)],
    "ireland": [f"H{i}" for i in range(1, 41)],
    "channel_islands": ["113"],
}


def get_region(vc_code: str) -> str:
    """Get region for a vice county code."""
    vc = str(vc_code)
    for region, codes in VC_REGIONS.items():
        if vc in codes:
            return region
    return "unknown"
