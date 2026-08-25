"""National India dataset for the synthetic groundwater demonstration.

Real administrative boundaries (states/union territories and their districts)
are combined with a deterministic synthetic village layer. Every village is
clearly labelled as demo data; nothing here is official IN-GRES/CGWB data.

All randomness is seeded (per district) so the generated dataset is stable
across runs and environments.
"""

from __future__ import annotations

import zlib
from functools import lru_cache

from app.gis.geo import district_placements, india_polygons, point_in_geometry

# ---------------------------------------------------------------------------
# States / union territories of India (name, code, region, centroid, spread,
# climate profile, village density multiplier).
# ---------------------------------------------------------------------------

# fmt: off
INDIA_STATES: list[dict] = [
    {"name": "Andhra Pradesh", "code": "AP", "region": "South India", "profile": "normal", "lat": 15.9, "lon": 79.7, "spread": 2.2, "density": 1.1, "suffix": "south"},
    {"name": "Arunachal Pradesh", "code": "AR", "region": "Northeast India", "profile": "wet", "lat": 28.2, "lon": 94.5, "spread": 2.3, "density": 0.35, "suffix": "northeast"},
    {"name": "Assam", "code": "AS", "region": "Northeast India", "profile": "wet", "lat": 26.3, "lon": 92.9, "spread": 1.8, "density": 1.3, "suffix": "northeast"},
    {"name": "Bihar", "code": "BR", "region": "East India", "profile": "normal", "lat": 25.6, "lon": 85.8, "spread": 1.7, "density": 2.0, "suffix": "east"},
    {"name": "Chhattisgarh", "code": "CG", "region": "Central India", "profile": "normal", "lat": 21.3, "lon": 81.6, "spread": 2.4, "density": 1.0, "suffix": "central"},
    {"name": "Goa", "code": "GA", "region": "West India", "profile": "wet", "lat": 15.3, "lon": 74.1, "spread": 0.3, "density": 0.4, "suffix": "west"},
    {"name": "Gujarat", "code": "GJ", "region": "West India", "profile": "dry", "lat": 22.5, "lon": 71.6, "spread": 3.3, "density": 1.1, "suffix": "west"},
    {"name": "Haryana", "code": "HR", "region": "North India", "profile": "dry", "lat": 29.1, "lon": 76.1, "spread": 1.1, "density": 1.7, "suffix": "north"},
    {"name": "Himachal Pradesh", "code": "HP", "region": "North India", "profile": "dry", "lat": 31.5, "lon": 77.1, "spread": 1.5, "density": 0.9, "suffix": "north"},
    {"name": "Jharkhand", "code": "JH", "region": "East India", "profile": "normal", "lat": 23.4, "lon": 85.3, "spread": 1.8, "density": 1.2, "suffix": "east"},
    {"name": "Karnataka", "code": "KA", "region": "South India", "profile": "normal", "lat": 14.6, "lon": 75.8, "spread": 2.6, "density": 1.3, "suffix": "south"},
    {"name": "Kerala", "code": "KL", "region": "South India", "profile": "wet", "lat": 10.5, "lon": 76.2, "spread": 1.4, "density": 1.4, "suffix": "south"},
    {"name": "Madhya Pradesh", "code": "MP", "region": "Central India", "profile": "dry", "lat": 23.5, "lon": 78.6, "spread": 3.2, "density": 1.1, "suffix": "central"},
    {"name": "Maharashtra", "code": "MH", "region": "West India", "profile": "normal", "lat": 19.6, "lon": 75.6, "spread": 3.4, "density": 1.2, "suffix": "west"},
    {"name": "Manipur", "code": "MN", "region": "Northeast India", "profile": "wet", "lat": 24.8, "lon": 93.9, "spread": 1.4, "density": 0.7, "suffix": "northeast"},
    {"name": "Meghalaya", "code": "ML", "region": "Northeast India", "profile": "wet", "lat": 25.5, "lon": 91.3, "spread": 1.4, "density": 0.6, "suffix": "northeast"},
    {"name": "Mizoram", "code": "MZ", "region": "Northeast India", "profile": "wet", "lat": 23.2, "lon": 92.8, "spread": 1.5, "density": 0.4, "suffix": "northeast"},
    {"name": "Nagaland", "code": "NL", "region": "Northeast India", "profile": "wet", "lat": 26.1, "lon": 94.5, "spread": 1.4, "density": 0.5, "suffix": "northeast"},
    {"name": "Odisha", "code": "OD", "region": "East India", "profile": "normal", "lat": 20.4, "lon": 84.8, "spread": 2.6, "density": 1.3, "suffix": "east"},
    {"name": "Punjab", "code": "PB", "region": "North India", "profile": "dry", "lat": 30.8, "lon": 75.8, "spread": 1.3, "density": 1.9, "suffix": "north"},
    {"name": "Rajasthan", "code": "RJ", "region": "North India", "profile": "dry", "lat": 26.9, "lon": 74.3, "spread": 3.7, "density": 0.8, "suffix": "north"},
    {"name": "Sikkim", "code": "SK", "region": "Northeast India", "profile": "wet", "lat": 27.5, "lon": 88.5, "spread": 1.0, "density": 0.5, "suffix": "northeast"},
    {"name": "Tamil Nadu", "code": "TN", "region": "South India", "profile": "normal", "lat": 10.8, "lon": 78.7, "spread": 2.2, "density": 1.5, "suffix": "south"},
    {"name": "Telangana", "code": "TS", "region": "South India", "profile": "normal", "lat": 18.0, "lon": 79.3, "spread": 1.6, "density": 1.2, "suffix": "south"},
    {"name": "Tripura", "code": "TR", "region": "Northeast India", "profile": "wet", "lat": 23.8, "lon": 91.6, "spread": 1.1, "density": 0.9, "suffix": "northeast"},
    {"name": "Uttar Pradesh", "code": "UP", "region": "North India", "profile": "dry", "lat": 27.2, "lon": 80.0, "spread": 2.8, "density": 2.2, "suffix": "north"},
    {"name": "Uttarakhand", "code": "UK", "region": "North India", "profile": "dry", "lat": 30.0, "lon": 78.9, "spread": 1.5, "density": 0.9, "suffix": "north"},
    {"name": "West Bengal", "code": "WB", "region": "East India", "profile": "wet", "lat": 23.2, "lon": 87.9, "spread": 1.9, "density": 1.8, "suffix": "east"},
    {"name": "Andaman and Nicobar Islands", "code": "AN", "region": "Island Territories", "profile": "wet", "lat": 11.7, "lon": 92.7, "spread": 1.6, "density": 0.3, "suffix": "islands"},
    {"name": "Chandigarh", "code": "CH", "region": "North India", "profile": "dry", "lat": 30.75, "lon": 76.78, "spread": 0.1, "density": 0.3, "suffix": "north"},
    {"name": "Dadra and Nagar Haveli and Daman and Diu", "code": "DN", "region": "West India", "profile": "wet", "lat": 20.3, "lon": 73.0, "spread": 0.4, "density": 0.3, "suffix": "west"},
    {"name": "Delhi", "code": "DL", "region": "North India", "profile": "dry", "lat": 28.6, "lon": 77.2, "spread": 0.5, "density": 0.3, "suffix": "north"},
    {"name": "Jammu and Kashmir", "code": "JK", "region": "North India", "profile": "dry", "lat": 33.8, "lon": 75.7, "spread": 2.3, "density": 0.7, "suffix": "north"},
    {"name": "Ladakh", "code": "LA", "region": "North India", "profile": "dry", "lat": 34.1, "lon": 77.6, "spread": 2.6, "density": 0.3, "suffix": "north"},
    {"name": "Lakshadweep", "code": "LD", "region": "Island Territories", "profile": "wet", "lat": 10.6, "lon": 72.6, "spread": 0.5, "density": 0.3, "suffix": "islands"},
    {"name": "Puducherry", "code": "PY", "region": "South India", "profile": "normal", "lat": 11.9, "lon": 79.8, "spread": 0.5, "density": 0.3, "suffix": "south"},
]
# fmt: on

# ---------------------------------------------------------------------------
# Real district names per state / UT (approx. current counts).
# ---------------------------------------------------------------------------

# fmt: off
DISTRICTS_BY_STATE: dict[str, list[str]] = {
    "Andhra Pradesh": ["Alluri Sitharama Raju", "Anakapalli", "Anantapur", "Annamayya", "Bapatla", "Chittoor", "East Godavari", "Eluru", "Guntur", "Kakinada", "Konaseema", "Krishna", "Kurnool", "Nandyal", "NTR", "Palnadu", "Parvathipuram Manyam", "Prakasam", "Srikakulam", "Sri Sathya Sai", "Tirupati", "Visakhapatnam", "Vizianagaram", "West Godavari", "YSR Kadapa"],
    "Arunachal Pradesh": ["Anjaw", "Changlang", "Dibang Valley", "East Kameng", "East Siang", "Itanagar Capital Complex", "Kamle", "Kra Daadi", "Kurung Kumey", "Lepa-Rada", "Lohit", "Longding", "Lower Dibang Valley", "Lower Siang", "Lower Subansiri", "Namsai", "Pakke-Kessang", "Papum Pare", "Shi-Yomi", "Siang", "Tawang", "Tirap", "Upper Siang", "Upper Subansiri", "West Kameng", "West Siang"],
    "Assam": ["Bajali", "Baksa", "Barpeta", "Biswanath", "Bongaigaon", "Cachar", "Charaideo", "Chirang", "Darrang", "Dhemaji", "Dhubri", "Dibrugarh", "Dima Hasao", "Goalpara", "Golaghat", "Hailakandi", "Hojai", "Jorhat", "Kamrup", "Kamrup Metropolitan", "Karbi Anglong", "Karimganj", "Kokrajhar", "Lakhimpur", "Majuli", "Marigaon", "Nagaon", "Nalbari", "Sivasagar", "Sonitpur", "South Salmara-Mankachar", "Tamulpur", "Tinsukia", "Udalguri", "West Karbi Anglong"],
    "Bihar": ["Araria", "Arwal", "Aurangabad", "Banka", "Begusarai", "Bhagalpur", "Bhojpur", "Buxar", "Darbhanga", "East Champaran", "Gaya", "Gopalganj", "Jamui", "Jehanabad", "Kaimur", "Katihar", "Khagaria", "Kishanganj", "Lakhisarai", "Madhepura", "Madhubani", "Munger", "Muzaffarpur", "Nalanda", "Nawada", "Patna", "Purnia", "Rohtas", "Saharsa", "Samastipur", "Saran", "Sheikhpura", "Sheohar", "Sitamarhi", "Siwan", "Supaul", "Vaishali", "West Champaran"],
    "Chhattisgarh": ["Balod", "Baloda Bazar", "Balrampur", "Bastar", "Bemetara", "Bijapur", "Bilaspur", "Dantewada", "Dhamtari", "Durg", "Gariaband", "Gaurella-Pendra-Marwahi", "Janjgir-Champa", "Jashpur", "Kanker", "Kabirdham", "Khairagarh-Chhuikhadan-Gandai", "Kondagaon", "Korba", "Koriya", "Mahasamund", "Manendragarh-Chirmiri-Bharatpur", "Mohla-Manpur-Ambagarh Chowki", "Mungeli", "Narayanpur", "Raigarh", "Raipur", "Rajnandgaon", "Sakti", "Sarangarh-Bilaigarh", "Sukma", "Surajpur", "Surguja"],
    "Goa": ["North Goa", "South Goa"],
    "Gujarat": ["Ahmedabad", "Amreli", "Anand", "Aravalli", "Banaskantha", "Bharuch", "Bhavnagar", "Botad", "Chhota Udepur", "Dahod", "Dang", "Devbhoomi Dwarka", "Gandhinagar", "Gir Somnath", "Jamnagar", "Junagadh", "Kutch", "Kheda", "Mahisagar", "Mehsana", "Morbi", "Narmada", "Navsari", "Panchmahal", "Patan", "Porbandar", "Rajkot", "Sabarkantha", "Surat", "Surendranagar", "Tapi", "Vadodara", "Valsad"],
    "Haryana": ["Ambala", "Bhiwani", "Charkhi Dadri", "Faridabad", "Fatehabad", "Gurugram", "Hisar", "Jhajjar", "Jind", "Kaithal", "Karnal", "Kurukshetra", "Mahendragarh", "Nuh", "Palwal", "Panchkula", "Panipat", "Rewari", "Rohtak", "Sirsa", "Sonipat", "Yamunanagar"],
    "Himachal Pradesh": ["Bilaspur", "Chamba", "Hamirpur", "Kangra", "Kinnaur", "Kullu", "Lahaul and Spiti", "Mandi", "Shimla", "Sirmaur", "Solan", "Una"],
    "Jharkhand": ["Bokaro", "Chatra", "Deoghar", "Dhanbad", "Dumka", "East Singhbhum", "Garhwa", "Giridih", "Godda", "Gumla", "Hazaribagh", "Jamtara", "Khunti", "Koderma", "Latehar", "Lohardaga", "Pakur", "Palamu", "Ramgarh", "Ranchi", "Sahibganj", "Seraikela Kharsawan", "Simdega", "West Singhbhum"],
    "Karnataka": ["Bagalkot", "Ballari", "Belagavi", "Bengaluru Rural", "Bengaluru Urban", "Bidar", "Chamarajanagar", "Chikkaballapura", "Chikkamagaluru", "Chitradurga", "Dakshina Kannada", "Davanagere", "Dharwad", "Gadag", "Hassan", "Haveri", "Kalaburagi", "Kodagu", "Kolar", "Koppal", "Mandya", "Mysuru", "Raichur", "Ramanagara", "Shivamogga", "Tumakuru", "Udupi", "Uttara Kannada", "Vijayapura", "Vijayanagara", "Yadgir"],
    "Kerala": ["Alappuzha", "Ernakulam", "Idukki", "Kannur", "Kasaragod", "Kollam", "Kottayam", "Kozhikode", "Malappuram", "Palakkad", "Pathanamthitta", "Thiruvananthapuram", "Thrissur", "Wayanad"],
    "Madhya Pradesh": ["Agar Malwa", "Alirajpur", "Anuppur", "Ashoknagar", "Balaghat", "Barwani", "Betul", "Bhind", "Bhopal", "Burhanpur", "Chachaura", "Chhatarpur", "Chhindwara", "Damoh", "Datia", "Dewas", "Dhar", "Dindori", "Guna", "Gwalior", "Harda", "Narmadapuram", "Indore", "Jabalpur", "Jhabua", "Katni", "Khandwa", "Khargone", "Maihar", "Mandla", "Mandsaur", "Morena", "Nagda", "Narsinghpur", "Neemuch", "Niwari", "Panna", "Raisen", "Rajgarh", "Ratlam", "Rewa", "Sagar", "Satna", "Sehore", "Seoni", "Shahdol", "Shajapur", "Sheopur", "Shivpuri", "Sidhi", "Singrauli", "Tikamgarh", "Ujjain", "Umaria", "Vidisha"],
    "Maharashtra": ["Ahmednagar", "Akola", "Amravati", "Chhatrapati Sambhajinagar", "Beed", "Bhandara", "Buldhana", "Chandrapur", "Dhule", "Gadchiroli", "Gondia", "Hingoli", "Jalgaon", "Jalna", "Kolhapur", "Latur", "Mumbai City", "Mumbai Suburban", "Nagpur", "Nanded", "Nandurbar", "Nashik", "Osmanabad", "Palghar", "Parbhani", "Pune", "Raigad", "Ratnagiri", "Sangli", "Satara", "Sindhudurg", "Solapur", "Thane", "Wardha", "Washim", "Yavatmal"],
    "Manipur": ["Bishnupur", "Chandel", "Churachandpur", "Imphal East", "Imphal West", "Jiribam", "Kakching", "Kamjong", "Kangpokpi", "Noney", "Pherzawl", "Senapati", "Tamenglong", "Tengnoupal", "Thoubal", "Ukhrul"],
    "Meghalaya": ["East Garo Hills", "East Jaintia Hills", "East Khasi Hills", "Eastern West Khasi Hills", "North Garo Hills", "Ri Bhoi", "South Garo Hills", "South West Garo Hills", "South West Khasi Hills", "West Garo Hills", "West Jaintia Hills", "West Khasi Hills"],
    "Mizoram": ["Aizawl", "Champhai", "Hnahthial", "Khawzawl", "Kolasib", "Lawngtlai", "Lunglei", "Mamit", "Saiha", "Saitual", "Serchhip"],
    "Nagaland": ["Chumoukedima", "Dimapur", "Kiphire", "Kohima", "Longleng", "Mokokchung", "Mon", "Niuland", "Noklak", "Peren", "Phek", "Shamator", "Tseminyu", "Tuensang", "Wokha", "Zunheboto"],
    "Odisha": ["Angul", "Balangir", "Balasore", "Bargarh", "Bhadrak", "Boudh", "Cuttack", "Debagarh", "Dhenkanal", "Gajapati", "Ganjam", "Jagatsinghpur", "Jajpur", "Jharsuguda", "Kalahandi", "Kandhamal", "Kendrapara", "Kendujhar", "Khordha", "Koraput", "Malkangiri", "Mayurbhanj", "Nabarangpur", "Nayagarh", "Nuapada", "Puri", "Rayagada", "Sambalpur", "Subarnapur", "Sundargarh"],
    "Punjab": ["Amritsar", "Barnala", "Bathinda", "Faridkot", "Fatehgarh Sahib", "Fazilka", "Firozpur", "Gurdaspur", "Hoshiarpur", "Jalandhar", "Kapurthala", "Ludhiana", "Malerkotla", "Mansa", "Moga", "Pathankot", "Patiala", "Rupnagar", "Sahibzada Ajit Singh Nagar", "Sangrur", "Shahid Bhagat Singh Nagar", "Sri Muktsar Sahib", "Tarn Taran"],
    "Rajasthan": ["Ajmer", "Alwar", "Anupgarh", "Balotra", "Banswara", "Baran", "Barmer", "Beawar", "Bharatpur", "Bhilwara", "Bikaner", "Bundi", "Chittorgarh", "Churu", "Dausa", "Deeg", "Didwana-Kuchaman", "Dholpur", "Dudu", "Dungarpur", "Gangapur City", "Hanumangarh", "Jaipur", "Jaipur Rural", "Jaisalmer", "Jalore", "Jhalawar", "Jhunjhunu", "Jodhpur", "Jodhpur Rural", "Karauli", "Kekri", "Khairthal-Tijara", "Kota", "Nagaur", "Neem Ka Thana", "Pali", "Phalodi", "Pratapgarh", "Rajsamand", "Salumbar", "Sanchore", "Sawai Madhopur", "Shahpura", "Sikar", "Sirohi", "Sri Ganganagar", "Tonk", "Udaipur"],
    "Sikkim": ["Gangtok", "Gyalshing", "Mangan", "Namchi", "Pakyong", "Soreng"],
    "Tamil Nadu": ["Ariyalur", "Chengalpattu", "Chennai", "Coimbatore", "Cuddalore", "Dharmapuri", "Dindigul", "Erode", "Kallakurichi", "Kanchipuram", "Kanyakumari", "Karur", "Krishnagiri", "Madurai", "Mayiladuthurai", "Nagapattinam", "Namakkal", "Nilgiris", "Perambalur", "Pudukkottai", "Ramanathapuram", "Ranipet", "Salem", "Sivaganga", "Tenkasi", "Thanjavur", "Theni", "Thoothukudi", "Tiruchirappalli", "Tirunelveli", "Tirupathur", "Tiruppur", "Tiruvallur", "Tiruvannamalai", "Tiruvarur", "Vellore", "Viluppuram", "Virudhunagar"],
    "Telangana": ["Adilabad", "Bhadradri Kothagudem", "Hanamkonda", "Hyderabad", "Jagtial", "Jangaon", "Jayashankar Bhupalpally", "Jogulamba Gadwal", "Kamareddy", "Karimnagar", "Khammam", "Komaram Bheem", "Mahabubabad", "Mahabubnagar", "Mancherial", "Medak", "Medchal-Malkajgiri", "Mulugu", "Nagarkurnool", "Nalgonda", "Narayanpet", "Nirmal", "Nizamabad", "Peddapalli", "Rajanna Sircilla", "Rangareddy", "Sangareddy", "Siddipet", "Suryapet", "Vikarabad", "Wanaparthy", "Warangal", "Yadadri Bhuvanagiri"],
    "Tripura": ["Dhalai", "Gomati", "Khowai", "North Tripura", "Sepahijala", "South Tripura", "Unakoti", "West Tripura"],
    "Uttar Pradesh": ["Agra", "Aligarh", "Ambedkar Nagar", "Amethi", "Amroha", "Auraiya", "Ayodhya", "Azamgarh", "Baghpat", "Bahraich", "Ballia", "Balrampur", "Banda", "Barabanki", "Bareilly", "Basti", "Bhadohi", "Bijnor", "Budaun", "Bulandshahr", "Chandauli", "Chitrakoot", "Deoria", "Etah", "Etawah", "Farrukhabad", "Fatehpur", "Firozabad", "Gautam Buddha Nagar", "Ghaziabad", "Ghazipur", "Gonda", "Gorakhpur", "Hamirpur", "Hapur", "Hardoi", "Hathras", "Jalaun", "Jaunpur", "Jhansi", "Kannauj", "Kanpur Dehat", "Kanpur Nagar", "Kasganj", "Kaushambi", "Kushinagar", "Lakhimpur Kheri", "Lalitpur", "Lucknow", "Maharajganj", "Mahoba", "Mainpuri", "Mathura", "Mau", "Meerut", "Mirzapur", "Moradabad", "Muzaffarnagar", "Pilibhit", "Pratapgarh", "Prayagraj", "Raebareli", "Rampur", "Saharanpur", "Sambhal", "Sant Kabir Nagar", "Shahjahanpur", "Shamli", "Shravasti", "Siddharthnagar", "Sitapur", "Sonbhadra", "Sultanpur", "Unnao", "Varanasi"],
    "Uttarakhand": ["Almora", "Bageshwar", "Chamoli", "Champawat", "Dehradun", "Haridwar", "Nainital", "Pauri Garhwal", "Pithoragarh", "Rudraprayag", "Tehri Garhwal", "Udham Singh Nagar", "Uttarkashi"],
    "West Bengal": ["Alipurduar", "Bankura", "Birbhum", "Cooch Behar", "Dakshin Dinajpur", "Darjeeling", "Hooghly", "Howrah", "Jalpaiguri", "Jhargram", "Kalimpong", "Kolkata", "Malda", "Murshidabad", "Nadia", "North 24 Parganas", "Paschim Bardhaman", "Paschim Medinipur", "Purba Bardhaman", "Purba Medinipur", "Purulia", "South 24 Parganas", "Uttar Dinajpur"],
    "Andaman and Nicobar Islands": ["North and Middle Andaman", "South Andaman", "Nicobar"],
    "Chandigarh": ["Chandigarh"],
    "Dadra and Nagar Haveli and Daman and Diu": ["Dadra and Nagar Haveli", "Daman", "Diu"],
    "Delhi": ["Central Delhi", "East Delhi", "New Delhi", "North Delhi", "North East Delhi", "North West Delhi", "Shahdara", "South Delhi", "South East Delhi", "South West Delhi", "West Delhi"],
    "Jammu and Kashmir": ["Anantnag", "Bandipora", "Baramulla", "Budgam", "Doda", "Ganderbal", "Jammu", "Kathua", "Kishtwar", "Kulgam", "Kupwara", "Pulwama", "Poonch", "Rajouri", "Ramban", "Reasi", "Samba", "Shopian", "Srinagar", "Udhampur"],
    "Ladakh": ["Kargil", "Leh"],
    "Lakshadweep": ["Lakshadweep"],
    "Puducherry": ["Karaikal", "Mahe", "Puducherry", "Yanam"],
}
# fmt: on

# ---------------------------------------------------------------------------
# Village name synthesis. Prefixes are shared across India; suffixes vary by
# region so generated names sound locally plausible (e.g. -palli in the south,
# -pur in the north, -gram in the east).
# ---------------------------------------------------------------------------

_PREFIXES: list[str] = [
    "Ram", "Krishna", "Gopal", "Lakshmi", "Sita", "Ravi", "Surya", "Chandra",
    "Bala", "Venkat", "Narasimha", "Govind", "Hanuman", "Shiva", "Ganesh",
    "Durga", "Lakshman", "Bharat", "Arjun", "Karan", "Mohan", "Madan", "Shyam",
    "Radha", "Jai", "Vijay", "Ajay", "Suraj", "Ratan", "Moti", "Hari", "Om",
    "Ganga", "Yamuna", "Godavari", "Narmada", "Kaveri", "Bhima", "Tunga",
    "Sagar", "Tala", "Bara", "Chota", "Mota", "Naya", "Purana", "Uttar",
    "Dakshin", "Prabhu", "Dev", "Kishan", "Soman", "Bhim", "Nand", "Kishor",
    "Mangal", "Shankar", "Madhav", "Vishnu", "Balram", "Dharma", "Kalyan",
    "Sundar", "Ranga", "Malla", "Peda", "Chinna", "Periya", "Kotta", "Putta",
    "Tirupati", "Anand", "Bhagat", "Ghanshyam", "Meera", "Bharati", "Saroj",
    "Pushpa", "Kaml", "Radhe", "Banke", "Thakur", "Lala", "Mian", "Ali",
    "Nur", "Fateh", "Sher", "Guru", "Dharam", "Sadh", "Pandit", "Jogi",
]

# region key -> list of village-name suffixes
_SUFFIXES: dict[str, list[str]] = {
    "south": [
        "palli", "pally", "peta", "puram", "pura", "kota", "gudem", "palem",
        "uru", "ooru", "halli", "kere", "patnam", "nagar", "vanam", "cheruvu",
        "madu", "kur", "thota", "vada", "guduru", "varam", "mal", "konda",
    ],
    "east": [
        "gram", "gaon", "pur", "para", "bati", "diha", "chak", "pada",
        "nagar", "hata", "tola", "khanda", "gachha", "bani", "bad", "maria",
    ],
    "north": [
        "pur", "nagar", "ganj", "garh", "khurd", "kalan", "sarai", "khera",
        "abad", "gaon", "wan", "bari", "pura", "khas", "wala", "kot",
        "bariya", "tola", "mau", "patti", "sadan", "thu", "hesa", "khera",
    ],
    "west": [
        "pur", "pura", "gadh", "wada", "vada", "nagar", "gaon", "vihir",
        "wadi", "khurd", "kheda", "amra", "i", "a", "pada", "nath",
    ],
    "central": [
        "pur", "pura", "kheda", "ganj", "badi", "tola", "mau", "garh",
        "nagar", "bhav", "was", "kala", "buzurg", "khurd", "sarai", "tola",
    ],
    "northeast": [
        "nagar", "gaon", "phang", "long", "sang", "gram", "kona", "para",
        "bari", "basti", "khullen", "bunglow", "hok", "the", "zor", "mukh",
    ],
    "islands": ["nagar", "gram", "pur", "kot", "tola", "bari", "para", "kala"],
}

# Roman ordinals for disambiguating generated names within a district.
_ORDINAL = ["", " II", " III", " IV", " V", " VI", " VII", " VIII", " IX", " X"]


def _hash_str(value: str) -> int:
    return zlib.crc32(value.encode("utf-8"))


def state_info(name: str) -> dict | None:
    for info in INDIA_STATES:
        if info["name"] == name:
            return info
    return None


def state_names() -> list[str]:
    return [s["name"] for s in INDIA_STATES]


def district_names(state_name: str) -> list[str]:
    return list(DISTRICTS_BY_STATE.get(state_name, []))


@lru_cache(maxsize=None)
def _district_placements_for(state_name: str) -> dict[str, tuple[float, float]]:
    return district_placements(state_name, DISTRICTS_BY_STATE.get(state_name, []))


def district_centroid(state_info_: dict, district_name: str) -> tuple[float, float]:
    """Deterministic representative point for a district.

    The point is placed inside the real state boundary polygon (from
    ``india_states.geojson``), so it is always on land inside the correct
    state -- never randomly in the sea or outside the boundary. Falls back to
    the old pseudo-centroid only when no polygon is available.
    """
    placed = _district_placements_for(state_info_["name"])
    if district_name in placed:
        return placed[district_name]
    rng = random_for(f"district:{district_name}")
    spread = state_info_["spread"]
    lat = state_info_["lat"] + rng.uniform(-spread, spread)
    lon = state_info_["lon"] + rng.uniform(-spread, spread)
    return round(lat, 4), round(lon, 4)


def random_for(key: str) -> object:
    import random

    return random.Random(_hash_str(key))


def village_count_for(district_name: str, density: float, per_district: int | None = None) -> int:
    """Number of villages to generate for a district.

    With ``per_district`` set the count is fixed; otherwise a density-weighted
    deterministic value (approx. 150-1800 per district, denser plains states
    get more). A full national run totals roughly 600,000 villages.
    """
    if per_district is not None and per_district > 0:
        return int(per_district)
    rng = random_for(f"count:{district_name}")
    base = rng.uniform(150, 900) * density
    return max(60, int(round(base)))


def generate_village_names(district_name: str, count: int, region_key: str) -> list[str]:
    """Deterministic, unique village names for a district."""
    suffixes = _SUFFIXES.get(region_key, _SUFFIXES["north"])
    rng = random_for(f"village:{district_name}")
    seen: set[str] = set()
    names: list[str] = []
    while len(names) < count:
        prefix = _PREFIXES[rng.randrange(len(_PREFIXES))]
        suffix = suffixes[rng.randrange(len(suffixes))]
        base = f"{prefix}{suffix}"
        if base in seen:
            base = f"{prefix}{suffix}{_ORDINAL[rng.randrange(1, len(_ORDINAL))]}"
        if base in seen:
            continue
        seen.add(base)
        names.append(base)
    return names


def generate_population(seed_key: str, low: int = 120, high: int = 20000) -> int:
    rng = random_for(f"pop:{seed_key}")
    # Log-normal-ish spread, clamped to a plausible village size.
    value = int(rng.expovariate(1.0 / 1800.0))
    return max(low, min(high, value))


def generate_village_coords(
    district_lat: float,
    district_lon: float,
    seed_key: str,
    spread: float = 0.35,
    geom: dict | None = None,
) -> tuple[float, float]:
    """Deterministic village point, guaranteed to stay inside the state land.

    Samples offsets around the district point and keeps the first one that is
    inside the real state polygon (``geom``). If no in-polygon sample is found
    within the attempt budget it returns the district point itself, which is
    already a valid interior point.
    """
    rng = random_for(f"coord:{seed_key}")
    for _ in range(25):
        lat = district_lat + rng.uniform(-spread, spread)
        lon = district_lon + rng.uniform(-spread, spread)
        if geom is None or point_in_geometry(lon, lat, geom):
            return round(lat, 5), round(lon, 5)
    return round(district_lat, 5), round(district_lon, 5)
