# %%
"""
TODO
- Tiles downloader maken
- 



"""


import functools
import sys
sys.path.insert(0, r'E:\github\wvangerwen\hhnk-research-tools') #import local hrt installation.
import importlib
import hhnk_research_tools as hrt
importlib.reload(hrt)

import geopandas as gpd
import pandas as pd
import os
import numpy as np
import matplotlib.pyplot as plt
import functions.wss_loading as wss_loading
import functions.wss_calculations as wss_calculations

importlib.reload(wss_loading)
importlib.reload(wss_calculations)


# %%

cfg_file = r'../01_data/schadetabel_hhnk_2020.cfg'
landuse_file = r'../01_data/landuse2019_tiles/waterland_landuse2019.vrt'
# depth_file =  r'../01_data/texel_80.tif'
# output_file = r'../01_data/damage_texel_80.tif'

depth_file = r'../01_data/marken_rev23_max_depth_blok_GGG_T10.tif'
output_file = r'../01_data/marken_rev23_damage_blok_GGG_T10.tif'


wss_settings = {'duur_uur': 48, #uren
                'herstelperiode':'10 dagen',
                'maand':'sep',
                'cfg_file':cfg_file}


dmg_table_landuse, dmg_table_general = wss_loading.read_dmg_table_config(wss_settings)

indices={}
indices['herstelperiode'] = dmg_table_general['herstelperiode'].index(wss_settings['herstelperiode'])
indices['maand'] = dmg_table_general['maand'].index(wss_settings['maand'])

lu_raster=None
depth_raster=None

lu_raster = hrt.Raster(landuse_file)
depth_raster = hrt.Raster(depth_file, min_block_size=2048)

blocks_df = depth_raster.generate_blocks()

#Create output raster
if not os.path.exists(output_file):
    print("creating output raster.")
    target_ds = hrt.create_new_raster_file(file_name=output_file,
        nodata=0,
        meta=depth_raster.metadata,)
    target_ds = None


dmg_table_landuse[0].gamma_inundatieduur_interp

# %%
from osgeo import gdal
gdal.UseExceptions()

class Waterschadeschatter():
    """Waterschadeschatter berekening van de schade bij een bepaalde inundatiediepte per 
    landgebruiksfunctie.
    wss_settings heeft onderstaand format. De naamgeving van herstelperiode en maand moet
    overeenkomen met de .cfg. De duur is een integer in uren. In de tabel vindt daarbij 
    lineare interpolatie plaats.
    wss_settings = {'duur_uur': '1 dag',
                'herstelperiode':'10 dagen',
                'maand':'sep',
                'cfg_file':cfg_file}"""

    def __init__(self, depth_file, landuse_file, output_file, wss_settings, min_block_size=2048):
        self.wss_settings = wss_settings
        self.min_block_size=min_block_size
        self.output_file = output_file
        self.lu_raster = hrt.Raster(landuse_file)
        self.depth_raster = hrt.Raster(depth_file, self.min_block_size)

        #Inladen configuratie
        self.dmg_table_landuse, self.dmg_table_general = wss_loading.read_dmg_table_config(self.wss_settings['cfg_file'])

        #Get indices
        self.indices = self.get_dmg_table_indices()


    def create_output_raster(self, verbose=True):
        #Create output raster
        if not os.path.exists(self.output_file):
            if verbose:
                print(f"creating output raster: {self.output_file}")
            target_ds = hrt.create_new_raster_file(file_name=self.output_file,
                nodata=0,
                meta=self.depth_raster.metadata,)
            target_ds = None
        else:
            if verbose:
                print(f"output raster already exists: {self.output_file}")


    def get_dmg_table_indices(self):
        indices={}
        indices['herstelperiode'] = self.dmg_table_general['herstelperiode'].index(self.wss_settings['herstelperiode'])
        indices['maand'] = self.dmg_table_general['maand'].index(self.wss_settings['maand'])
        return indices


    def dx_dy_between_rasters(self, meta_big, meta_small):
        #TODO add to hhnk_research_tools
        """create window to subset a large 2-d array with a smaller rectangle. Usage:
        shapes_array[dy_min:dy_max, dx_min:dx_max]
        window=create_array_window_from_meta(meta_big, meta_small)
        shapes_array[window]"""
        if meta_small['pixel_width'] != meta_big['pixel_width']:
            raise Exception(f"""Input rasters dont have same resolution. 
                    meta_big   = {meta_big['pixel_width']}m
                    meta_small = {meta_small['pixel_width']}m""")

        dx_min = max(0, int((meta_small['x_min']-meta_big['x_min'])/meta_big['pixel_width']))
        dy_min = max(0, int((meta_big['y_max']-meta_small['y_max'])/meta_big['pixel_width']))
        dx_max = int(min(dx_min + meta_small['x_res'], meta_big['x_res']))
        dy_max = int(min(dy_min + meta_small['y_res'], meta_big['y_res']))
        return dx_min, dy_min


    def calculate_damage_raster(self):
        target_ds=gdal.Open(self.output_file, gdal.GA_Update)
        dmg_band = target_ds.GetRasterBand(1)

        #Difference between landuse and depth raster.
        dx_min, dy_min = self.dx_dy_between_rasters(meta_big=self.lu_raster.metadata, meta_small=self.depth_raster.metadata)

        pixel_factor = self.depth_raster.pixelarea
        blocks_df = self.depth_raster.generate_blocks()

        len_total = len(blocks_df)
        for idx, block_row in blocks_df.iterrows():
                #Load landuse 
                window_depth=block_row['window_readarray']

                window_lu = window_depth.copy()
                window_lu[0] += dx_min
                window_lu[1] += dy_min

                lu_block = self.lu_raster._read_array(window=window_lu)
                lu_block = lu_block.astype(int)
                lu_block[lu_block==self.lu_raster.nodata] = 0
                if lu_block.mean()!=0:
                    # Load depth
                    depth_block = self.depth_raster._read_array(window=window_depth)
                    depth_block[depth_block==self.depth_raster.nodata] = 0

                    #Calculate damage
                    damage_block=wss_calculations.calculate_damage(lu_block=lu_block, 
                                                depth_block=depth_block, 
                                                indices=self.indices, 
                                                dmg_table_landuse=self.dmg_table_landuse, 
                                                dmg_table_general=self.dmg_table_general, 
                                                pixel_factor=pixel_factor)

                    #Write to file
                    dmg_band.WriteArray(damage_block, xoff=window_depth[0], yoff=window_depth[1])
                print(f"{idx} / {len_total}", end= '\r')
                # break
                

        dmg_band.FlushCache()  # close file after writing
        dmg_band = None
        target_ds = None


    def __repr__(self):
        """List available objects, distinction between functions and variables"""
        funcs = '.'+' .'.join([i for i in dir(self) if not i.startswith('__') and hasattr(getattr(self,i)
        , '__call__')])
        variables = '.'+' .'.join([i for i in dir(self) if not i.startswith('__') and not hasattr(getattr(self,i)
        , '__call__')])
        repr_str = f"""functions: {funcs}
variables: {variables}"""
        return repr_str

# %%

self = Waterschadeschatter(depth_file=depth_file, 
                            landuse_file=landuse_file, 
                            output_file=output_file,
                            wss_settings=wss_settings)

# Aanmaken leeg output raster.
# self.create_output_raster()

# # #Berkenen schaderaster
# self.calculate_damage_raster()



# %%
lu_block=lu_block
depth_block=depth_block
indices=self.indices
dmg_table_landuse=self.dmg_table_landuse
dmg_table_general=self.dmg_table_general
pixel_factor=pixel_factor




# %%
depth = 0.0142824
#dmg_lizard = 0.00752583
# dmg_wss = 0.006045
# landuse=157 weidehooi
direct_gem = 1209/10000 #1209/ha
inderect_gem=0

gamma_inundatiediepte = 1
gamma_inundatieduur = 0.2
gamma_maand = 1
pixel_factor=0.25

direct_gem*gamma_inundatiediepte*gamma_inundatieduur*gamma_maand*pixel_factor











# %%
plt.imshow(depth_block)
plt.imshow(lu_block)
# %% 
a=None
dmg_raster = None
dmg_raster = hrt.Raster(output_file)
a=dmg_raster._read_array()
np.sum(a)










# %%

def landuse_not_in_cfg():
    """Check if any landuse is not in the cfg table"""
    no_landuse = np.isin(lu_block,[i for i in dmg_table_landuse.keys()])
    return np.unique(lu_block[~no_landuse])


# %%

%load_ext line_profiler
%lprun -f calculate_damage calculate_damage(lu_block, depth_block, indices, dmg_table_landuse, dmg_table_general)


#%%






# %%
def calculate_depth(dem, peilgebied_df, ws):
    """Bereken de inundatiediepte
    dem -> raster
    peilgebied_df -> shapefile met kolom 'streefpeil'. 
    ws -> int ws stijging tov streefpeil"""



def calculate_damage(depth_array, landuse_array, damage_table):
    """Bereken de schade
    depth -> raster
    landuse -> raster
    damage_table -> df of dict van df

    schade = max. directe schade · γdiepte · γduur · γseizoen + indirecte schade per dag · hersteltijd
    TODO indirecte schade nemen we nu niet mee.
    """

    for pixel in depth_array:
        'bereken schade per pixel.'