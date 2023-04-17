"""
Klaarzetten van de landgebruiksrasters.

"""


# %%
import threedi_scenario_downloader.downloader as dl
import os
import geopandas as gpd
from osgeo import gdal
import getpass
import numpy as np
# from functions.create_folders_dict import create_folders_dict_wss
# import functions.wsa_tools as wsa #general tools used across all scripts
import hhnk_research_tools as hrt
from local_settings import API_KEY
# %%
# this allows GDAL to throw Python Exceptions
gdal.UseExceptions()

dl.set_api_key(API_KEY)

#uuid of raster
uuids={}
# uuids['landgebruik'] = 'b73189fc-058d-4351-9b20-2538248fae4f'
uuids['landgebruik2019_3di'] = 'a80a6d31-f539-4037-9765-4fb880654424' #Deze wordt gebruikt in de 3Di nabewerking schadeberekening. Dat is hier terug te vinden; https://api.3di.live/v3.0/simulations/113368/results/post_processing/lizard/overview/
# uuids['landuse2018'] = '7a93a6de-680d-41ca-8e7a-4b356baa18c7'
# uuids['landuse2019'] = '169853de-8319-4a7f-b076-f2ee0ae5b8c4'
# uuids['landuse2020'] = 'afedc34b-427e-4fd1-ac19-ba83032e2407'
# uuids['landuse2021'] = '59064cc0-a0a2-4509-b790-e112cb718100'


# uuids['ahn3'] = '36588275-f3e3-4120-8c1e-602f7ae85386' #Deze is niet meer te vinden maar wel gebruikt in de schadeberekening van 2020. 
# uuids['ahn3'] = '81ef31b1-a65c-4071-acce-c77a172ba8a9'

output_dir={}
output_dir['landgebruik2019_3di'] = r'E:\01.basisgegevens\hhnk_schadeschatter\01_data\landuse2019_3di_tiles'
output_dir['landuse2019'] = r'E:\01.basisgegevens\hhnk_schadeschatter\01_data\landuse2019_tiles'
output_dir['landuse2020'] = r'E:\01.basisgegevens\hhnk_schadeschatter\01_data\landuse2020_tiles'
output_dir['landuse2021'] = r'E:\01.basisgegevens\hhnk_schadeschatter\01_data\landuse2021_tiles'

#resolution of output raster.
RESOLUTION = 0.5 #m
CHUNKSIZE = 5000
    
#outputloc
outDirs = {}
scenario_uuid=[]
resolution=RESOLUTION
bounds=[]
pathname=[]
raster_code=[]
is_threedi_scenario=[]
cont=False

#Boundaries for download
bounds_hhnk = {'west': 100500.0,
  'south': 486900.0,
  'east': 150150.0,
  'north': 577550.0}



xres = (bounds_hhnk['east']-bounds_hhnk['west'])/RESOLUTION
yres = (bounds_hhnk['north']-bounds_hhnk['south'])/RESOLUTION

for key, uuid in uuids.items(): 
            
    #Check if tiles are on system.
    for i in range(0,int(np.ceil(xres/CHUNKSIZE))):
        for j in range(0,int(np.ceil(yres/CHUNKSIZE))):

            #Split raster into smaller chuncks.
            b={'west':bounds_hhnk['west'] + i*CHUNKSIZE*RESOLUTION,
                'south':bounds_hhnk['south']+ j*CHUNKSIZE*RESOLUTION,
                'east':min(bounds_hhnk['west'] + (i+1)*CHUNKSIZE*RESOLUTION, bounds_hhnk['east']),
                'north':min(bounds_hhnk['south']+ (j+1)*CHUNKSIZE*RESOLUTION, bounds_hhnk['north'])}
            output_file = os.path.join(output_dir[key], f'{key}_x{str(i).zfill(2)}_y{str(j).zfill(2)}.tif')
            #Opsplitsen in kleinere gebieden
            if not os.path.exists(output_file):
                bounds.append(b)
                scenario_uuid.append(uuid)
                pathname.append(output_file)
                raster_code.append('')
                is_threedi_scenario.append(False)
            else: print('{} already on system'.format(output_file.split(os.sep)[-1]))

    if not os.path.exists(output_dir[key]):
        os.mkdir(output_dir[key])
    # #Create task and download rasters
    if len(pathname) != 0:
        cont = input(f'Start downloading {len(pathname)} tiles. \nContinue? [y/n]')



# %% Download

blocks=[slice(i,min(i+25,len(pathname))) for i in range(0, len(pathname),25)]

for block in blocks:
    print(block)
    for key, uuid in uuids.items(): 
        if cont=='y':
            print('Start download')   

            dl.download_raster(scenario=scenario_uuid[block],
                            raster_code = raster_code[block],
                            target_srs  = "EPSG:28992",
                            resolution  = resolution,
                            bounds      = bounds[block],
                            bounds_srs  = "EPSG:28992",
                            pathname    = pathname[block],
                            is_threedi_scenario = is_threedi_scenario[block])
                            
# %% Create VRT
for key, uuid in uuids.items(): 
    hrt.build_vrt(output_dir[key], bandlist=None, overwrite=True)
