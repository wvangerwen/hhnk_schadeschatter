import sys
from pathlib import Path
import os

if str(Path(os.getcwd()).parent.parent) not in sys.path:
    sys.path.append(str(Path(os.getcwd()).parent.parent))

import hhnk_schadeschatter.local_settings as local_settings
local_settings.fix_path()

import importlib
import hhnk_research_tools as hrt
importlib.reload(hrt)

import hhnk_schadeschatter.functions.wss_loading as wss_loading
import hhnk_schadeschatter.functions.wss_calculations as wss_calculations

from osgeo import gdal
gdal.UseExceptions()

DMG_NODATA = 0

class Waterschadeschatter():
    """Waterschadeschatter berekening van de schade bij een bepaalde inundatiediepte per 
    landgebruiksfunctie.
    wss_settings heeft onderstaand format. De naamgeving van herstelperiode en maand moet
    overeenkomen met de .cfg. De duur is een integer in uren. In de tabel vindt daarbij 
    lineare interpolatie plaats.
    wss_settings = {'duur_uur': 48, #uren
                'herstelperiode':'10 dagen',
                'maand':'sep',
                'cfg_file':cfg_file}
                
    LET OP: depth_file heeft dieptes nodig vanaf -0.01cm, zoals in .cfg ook staat. Dit moet
    dus ook meegenomen bij de vertaling van waterstand naar waterdiepte. 
    """

    def __init__(self, depth_file, landuse_file, output_file, wss_settings, min_block_size=2048):
        self.wss_settings = wss_settings
        self.min_block_size=min_block_size
        self.output_file = output_file
        self.lu_raster = hrt.Raster(landuse_file)
        self.depth_raster = hrt.Raster(depth_file, self.min_block_size)

        #Inladen configuratie
        self.dmg_table_landuse, self.dmg_table_general = wss_loading.read_dmg_table_config(self.wss_settings)

        #Get indices
        self.indices = self.get_dmg_table_indices()


    def create_output_raster(self, verbose=True, overwrite=False):
        """Create empty damage output raster"""
        #Check if function should continue.
        cont=True
        if not overwrite and os.path.exists(self.output_file):
            cont=False
            

        if cont==True:
            if verbose:
                print(f"creating output raster: {self.output_file}")
            target_ds = hrt.create_new_raster_file(file_name=self.output_file,
                                                    nodata=DMG_NODATA,
                                                    meta=self.depth_raster.metadata,)
            target_ds = None
        else:
            if verbose:
                print(f"output raster already exists: {self.output_file}")


    def get_dmg_table_indices(self):
        """Check the index in the table using the input values for herstelperiode and maand."""
        indices={}
        indices['herstelperiode'] = self.dmg_table_general['herstelperiode'].index(self.wss_settings['herstelperiode'])
        indices['maand'] = self.dmg_table_general['maand'].index(self.wss_settings['maand'])
        return indices


    def run(self, initialize_output=True):

        if initialize_output:
            self.create_output_raster(verbose=True)
        else:
            if not os.path.exists(self.output_file):
                print(f'Output {self.output_file} does not exist. Run this function with initialize_output=True')
                return

        target_ds=gdal.Open(self.output_file, gdal.GA_Update)
        dmg_band = target_ds.GetRasterBand(1)

        #Difference between landuse and depth raster.
        dx_min, dy_min = hrt.dx_dy_between_rasters(meta_big=self.lu_raster.metadata, meta_small=self.depth_raster.metadata)

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
                    # depth_mask = depth_block==self.depth_raster.nodata
                    # depth_block[depth_mask] = np.nan #Schadetabel loopt vanaf -0.01cm

                    #Calculate damage
                    damage_block=wss_calculations.calculate_damage(caller = self,
                                                lu_block=lu_block, 
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


if __name__ == '__main__':


    if False:
        #Variables
        cfg_file = r'../01_data/schadetabel_hhnk_2020.cfg'
        landuse_file = r'../01_data/landuse2019_tiles/waterland_landuse2019.vrt'

        depth_file = r'../01_data/marken_rev23_max_depth_blok_GGG_T10.tif'
        output_file = r'../01_data/marken_rev23_damage_blok_GGG_T10.tif'


        wss_settings = {'duur_uur': 48, #uren
                        'herstelperiode':'10 dagen',
                        'maand':'sep',
                        'cfg_file':cfg_file}

        #Calculation
        wss_local = Waterschadeschatter(depth_file=depth_file, 
                                landuse_file=landuse_file, 
                                output_file=output_file,
                                wss_settings=wss_settings)

        # # Aanmaken leeg output raster.
        wss_local.create_output_raster()

        # # #Berkenen schaderaster
        wss_local.calculate_damage_raster()