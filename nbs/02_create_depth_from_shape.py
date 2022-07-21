# %%
import sys
sys.path.append('../..')
import hhnk_schadeschatter.local_settings as local_settings
if local_settings.DEBUG:
    sys.path.insert(0, local_settings.hhnk_threedi_tools_path)
    sys.path.insert(0, local_settings.hhnk_research_tools_path)

    import importlib
    import hhnk_threedi_tools as htt
    import hhnk_research_tools as hrt
    htt=importlib.reload(htt)
    hrt=importlib.reload(hrt)
    importlib.reload(htt.core.folders)


import importlib
import hhnk_threedi_tools as htt
import hhnk_research_tools as hrt

import geopandas as gpd
import pandas as pd
import os
import numpy as np
import matplotlib.pyplot as plt
import hhnk_schadeschatter.functions.wss_loading as wss_loading
import hhnk_schadeschatter.functions.wss_calculations as wss_calculations
import hhnk_schadeschatter.functions.wss_main as wss_main
import hhnk_schadeschatter.functions.add_to_hrt as hrt_temp

importlib.reload(wss_main)
importlib.reload(wss_loading)
importlib.reload(wss_calculations)

from osgeo import gdal
gdal.UseExceptions()

from pathlib import Path


# %%
from shapely.geometry import box

pgb_all_path = r'E:\github\wvangerwen\hhnk_schadeschatter\01_data\peilgebieden_indeling.shp'
dem_path = r"G:\02_Werkplaatsen\06_HYD\Projecten\HKC16015 Wateropgave 2.0\11. DCMB\hhnk-modelbuilder-master\data\fixed_data\DEM\DEM_AHN4_int.vrt"
dem_path = r"\\srv57d1\geo_info\02_Werkplaatsen\06_HYD\Projecten\HKC21002 Schadecurven\07. SchadecurvenPy\03_gebieden\06_ad\03_downloads\ahn3_tiles\combined_rasters.vrt"
output_dir = r"E:\github\wvangerwen\hhnk_schadeschatter\01_data\drainage_areas"
dem_raster = hrt.Raster(dem_path)
gdf = gpd.read_file(pgb_all_path)

gdf['dirname'] = gdf.apply(lambda x: f"pgb_{x['id']}_{x['code']}", axis=1)
gdf['boxarea'] = gdf.bounds.apply(lambda x: box(*x).area, axis=1)


ws_range = range(0,260, 10)
class PgbFolder(htt.core.folders.Folder):
    def __init__(self, base):
        super().__init__(base)

        for ws in ws_range:
            self.add_file(objectname=f"ws_{ws}",
                            filename=f"ws_{ws}.tif",
                            ftype='raster')
            self.add_file(objectname=f"depth_{ws}",
                            filename=f"depth_{ws}.tif",
                            ftype='raster')
            self.add_file(objectname=f"dmg_{ws}",
                            filename=f"dmg_{ws}.tif",
                            ftype='raster')                            
# %%
# ~~ bereken waterstand ~~ #
for index, row in gdf.iterrows():
    if row['boxarea'] > 50000000:
        #TODO find solution for bigger areas
        continue
    else:

        pgb_folder = PgbFolder(base=os.path.join(output_dir, row['dirname']))
        pgb_gdf = gpd.GeoDataFrame(row).T
        
        meta=hrt.create_meta_from_gdf(gdf=pgb_gdf, res=dem_raster.metadata['pixel_width'])
        for ws in ws_range:
            pgb_gdf['wlvl'] = pgb_gdf['streefpeil']+ ws/100

            wlvl_array = hrt.gdf_to_raster(gdf=pgb_gdf,
                value_field='wlvl',
                raster_out=getattr(pgb_folder, f'ws_{ws}').path,
                nodata=-9999,
                metadata=meta,
                read_array=False)
        break


# %%

class Raster_calculator():
    """Make a custom calculation between two rasters by 
    reading the blocks and applying a calculation
    input raster should be of type hhnk_research_tools.gis.raster.Raster
    
    """
    def __init__(self, raster1, raster2, raster_out):

        self.raster_big, self.raster_small = self._checkbounds(raster1, raster2) 
        self.raster_out = raster_out

        #dx dy between rasters.
        self.dx_min, self.dy_min = hrt_temp.dx_dy_between_rasters(meta_big=self.raster_big.metadata, meta_small=self.raster_small.metadata)
        
        self.blocks_df = self.raster_small.generate_blocks()
        self.blocks_total = len(self.blocks_df)


    def _checkbounds(self, raster1, raster2):
        x1, x2, y1, y2=raster1.metadata['bounds']
        xx1, xx2, yy1, yy2=raster1.metadata['bounds']
        bounds_diff = x1 - xx1, y1 - yy1, xx2-x2, yy2 - y2 #subtract bounds
        check_arr = np.array([i<=0 for i in bounds_diff]) #check if values <=0

        #If all are true (or all false) we know that the rasters fully overlap. 
        if raster1.metadata['pixel_width'] != raster2.metadata['pixel_width']:
            raise Exception("""Rasters do not have equal resolution""")

        if np.all(check_arr):
            #In this case raster1 is the bigger raster.
            return raster1, raster2
        elif np.all(~check_arr):
            #Here raster2 is the bigger raster
            return raster2, raster1
        else:
            raise Exception("""Raster bounds do not overlap. We cannot use this.""")
        

    def create(self, verbose=True, overwrite=False, nodata=0):
        """Create empty output raster"""
        #Check if function should continue.
        cont=True
        if not overwrite and os.path.exists(self.raster_out.source_path):
            cont=False

        if cont==True:
            if verbose:
                print(f"creating output raster: {self.raster_out.source_path}")
            target_ds = hrt.create_new_raster_file(file_name=self.raster_out.source_path,
                                                    nodata=nodata,
                                                    meta=self.raster_small.metadata,)
            target_ds = None
        else:
            if verbose:
                print(f"output raster already exists: {self.raster_out.source_path}")


    def run(self, **kwargs):
        """loop over the small raster blocks, load both arrays and apply a custom function to it."""
        target_ds=gdal.Open(self.raster_out.source_path, gdal.GA_Update)
        band_out = target_ds.GetRasterBand(1)


        for idx, block_row in self.blocks_df.iterrows():
                #Load landuse 
                window_small=block_row['window_readarray']

                window_big = window_small.copy()
                window_big[0] += self.dx_min
                window_big[1] += self.dy_min

                self.custom_run(self=self, window_small=window_small, window_big=window_big, band_out=band_out, **kwargs)
                print(f"{idx} / {self.blocks_total}", end= '\r')
                # break
                
        band_out.FlushCache()  # close file after writing
        band_out = None
        target_ds = None




# %%
# ~~ bereken waterdiepte~~ #
def calculate_depth(self, window_small, window_big, band_out):
    """calculate depth for pgb 
    raster_big=dem
    raster_small=pgb. Should be added to Raster_calculator.custom_run
    then use Raster_calculator.run to run this function.
    """
    #Load windows
    block_big = self.raster_big._read_array(window=window_big)
    block_small = self.raster_small._read_array(window=window_small)

    #Calculate output
    block_out = block_small-block_big
    block_out[block_out<=-0.01] = self.raster_out.nodata  #depth array should run from -1cm to max depth. 
    #At -1 the dmg table starts.

    # Mask output   
    block_out[block_big==self.raster_big.nodata] = self.raster_out.nodata
    block_out[block_small==self.raster_small.nodata] = self.raster_out.nodata

    # Write to file
    band_out.WriteArray(block_out, xoff=window_small[0], yoff=window_small[1])


for index, row in gdf.iterrows():
    if row['boxarea'] > 50000000:
        #TODO find solution for bigger areas
        continue
    else:

        pgb_folder = PgbFolder(base=os.path.join(output_dir, row['dirname']))       
        for ws in ws_range:
            # if ws==250:
                ws_raster = hrt.Raster(getattr(pgb_folder, f'ws_{ws}').path)
                raster_depth = hrt.Raster(getattr(pgb_folder, f'depth_{ws}').path)

                if ws_raster.exists:
                    depth_calc = Raster_calculator(raster1=dem_raster, raster2=ws_raster, raster_out=raster_depth)
                    depth_calc.create(nodata=-9999, overwrite=False, verbose=False)
                    depth_calc.custom_run = calculate_depth
                    depth_calc.run()


    break
            # break
            #     #Inlezen van DEM met juiste window
            #     depth_array = dem_raster._read_array(window=window)




# %%

cfg_file = r'../01_data/schadetabel_hhnk_2020.cfg'
landuse_file = r'../01_data/landuse2019_tiles/waterland_landuse2019.vrt'
landuse_file = r"\\srv57d1\geo_info\02_Werkplaatsen\06_HYD\Projecten\HKC21002 Schadecurven\07. SchadecurvenPy\03_gebieden\06_ad\03_downloads\landuse2019_tiles\ad_landuse2019.vrt"

wss_settings = {'duur_uur': 24, #uren
                'herstelperiode':'10 dagen',
                'maand':'sep',
                'cfg_file':cfg_file}


for index, row in gdf.iterrows():
    if row['boxarea'] > 50000000:
        #TODO find solution for bigger areas
        continue
    else:

        pgb_folder = PgbFolder(base=os.path.join(output_dir, row['dirname']))       
        for ws in ws_range:
            # if ws==250:
                ws_raster = hrt.Raster(getattr(pgb_folder, f'ws_{ws}').path)
                raster_depth = hrt.Raster(getattr(pgb_folder, f'depth_{ws}').path)

                wss_local = wss_main.Waterschadeschatter(depth_file=getattr(pgb_folder, f'depth_{ws}').path, 
                                            landuse_file=landuse_file, 
                                            output_file=getattr(pgb_folder, f'dmg_{ws}').path,
                                            wss_settings=wss_settings)
                wss_local.create_output_raster() # Aanmaken leeg output raster.
                wss_local.run(initialize_output=False) #Berekenen schaderaster

    break


