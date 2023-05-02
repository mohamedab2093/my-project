#git -C /odoo/odoo-server/aldabboos-addons pull https://github.com/elbasri/aldabboos-addons.git
cd /root/addons/
rm -rf /root/addons/*
#git clone -b test https://elbasri:***@github.com/elbasri/aldabboos-addons.git
git clone -b test https://mohamedab2093:***@github.com/mohamedab2093/aldabboos.git
[ -d "/root/addons/aldabboos/aldabboos-addons" ] && rm -rf /odoo/odoo-server/workingaddons/aldabboos-addons && cp -r /root/addons/aldabboos/aldabboos-addons /odoo/odoo-server/workingaddons/
[ -d "/root/addons/aldabboos/aldabboos-addons1" ] && rm -rf /odoo/odoo-server/workingaddons/aldabboos-addons1 && cp -r /root/addons/aldabboos/aldabboos-addons1 /odoo/odoo-server/workingaddons/
[ -d "/root/addons/aldabboos/aldabboos-addons2" ] && rm -rf /odoo/odoo-server/workingaddons/aldabboos-addons2 && cp -r /root/addons/aldabboos/aldabboos-addons2 /odoo/odoo-server/workingaddons/
[ -d "/root/addons/aldabboos/aldabboos-addons3" ] && rm -rf /odoo/odoo-server/workingaddons/aldabboos-addons3 && cp -r /root/addons/aldabboos/aldabboos-addons3 /odoo/odoo-server/workingaddons/
[ -d "/root/addons/aldabboos/aldabboos-addons4" ] && rm -rf /odoo/odoo-server/workingaddons/aldabboos-addons4 && cp -r /root/addons/aldabboos/aldabboos-addons4 /odoo/odoo-server/workingaddons/
[ -d "/root/addons/aldabboos/aldabboos-addons5" ] && rm -rf /odoo/odoo-server/workingaddons/aldabboos-addons5 && cp -r /root/addons/aldabboos/aldabboos-addons5 /odoo/odoo-server/workingaddons/
[ -d "/root/addons/aldabboos/hms" ] && rm -rf /odoo/odoo-server/workingaddons/hms && cp -r /root/addons/aldabboos/hms /odoo/odoo-server/workingaddons/
[ -d "/root/addons/aldabboos/hotels" ] && rm -rf /odoo/odoo-server/workingaddons/hotels && cp -r /root/addons/aldabboos/hotels /odoo/odoo-server/workingaddons/
[ -d "/root/addons/aldabboos/pharma" ] && rm -rf /odoo/odoo-server/workingaddons/pharma && cp -r /root/addons/aldabboos/pharma /odoo/odoo-server/workingaddons/

