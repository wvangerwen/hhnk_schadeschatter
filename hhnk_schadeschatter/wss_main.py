# %%
import importlib
import os

import hhnk_research_tools as hrt

import hhnk_schadeschatter.local_settings as local_settings

# local_settings.fix_path()

importlib.reload(hrt)

from osgeo import gdal

import hhnk_schadeschatter.wss_calculations as wss_calculations
import hhnk_schadeschatter.wss_loading as wss_loading

gdal.UseExceptions()

DMG_NODATA = 0

class Waterschadeschatter():
    """Waterschadeschatter berekening van de schade bij een bepaalde inundatiediepte per 
    landgebruiksfunctie.
    wss_settings heeft onderstaand format. De naamgeving van herstelperiode en maand moet
    overeenkomen met de .cfg. De duur is een integer in uren. In de tabel vindt daarbij 
    lineare interpolatie plaats.
    wss_settings = {'inundation_period': 48, #uren
                'herstelperiode':'10 dagen',
                'maand':'sep',
                'cfg_file':cfg_file,
                'dmg_type':'gem'} 

    dmg_type in ["min", "gem", "max"]
                
    LET OP: depth_file heeft dieptes nodig vanaf -0.01cm, zoals in .cfg ook staat. Dit moet
    dus ook meegenomen bij de vertaling van waterstand naar waterdiepte. 
    """

    def __init__(self, 
                 depth_file, 
                 landuse_file, 
                 wss_settings, 
                 min_block_size=2048, ):
        self.wss_settings = wss_settings
        self.min_block_size=min_block_size
        self.lu_raster = hrt.Raster(landuse_file)
        self.depth_raster = hrt.Raster(depth_file, self.min_block_size)
        self.gamma_inundatiediepte = None
        
        self.validate()

        #Inladen configuratie
        self.dmg_table_landuse, self.dmg_table_general = wss_loading.read_dmg_table_config(self.wss_settings)

        #Get indices
        self.indices = self.get_dmg_table_indices()


    def validate(self):
        """check if input exists"""
        for filepath in [self.lu_raster.pl, self.depth_raster.pl]:
            if not os.path.exists(filepath):
                raise Exception(f"could not find input file in: {filepath}")


    # def create_output_raster(self, output_raster, verbose=False, overwrite=False):
    #     """Create empty damage output raster"""
    #     #Check if function should continue.
    #     cont=True
    #     if not overwrite and os.path.exists(output_raster):
    #         cont=False
            

    #     if cont==True:
    #         if verbose:
    #             print(f"creating output raster: {output_raster}")
    #         target_ds = hrt.create_new_raster_file(file_name=output_raster.name,
    #                                                 nodata=DMG_NODATA,
    #                                                 meta=self.depth_raster.metadata,)
    #         target_ds = None
    #     else:
    #         if verbose:
    #             print(f"output raster already exists: {output_file}")


    def get_dmg_table_indices(self):
        """Check the index in the table using the input values for herstelperiode and maand."""
        indices={}
        indices['herstelperiode'] = self.dmg_table_general['herstelperiode'].index(self.wss_settings['herstelperiode'])
        indices['maand'] = self.dmg_table_general['maand'].index(self.wss_settings['maand'])
        return indices


    def run(self, 
            output_raster:hrt.Raster, 
            calculation_type="sum", 
            verbose=False, 
            overwrite=False,
            ):
        """
        Calculation type options: 'sum','direct','indirect'
        """

        if output_raster.exists:
            if overwrite is False:
                return
            else:
                output_raster.pl.unlink()

        #Create output raster
        output_raster.create(metadata=self.depth_raster.metadata,
                                nodata=DMG_NODATA, 
                                verbose=verbose, 
                                overwrite=overwrite)

        #Load raster so we can edit it.
        target_ds=output_raster.open_gdal_source_write()
        dmg_band = target_ds.GetRasterBand(1)

        #Difference between landuse and depth raster.
        dx_min, dy_min, dx_max, dy_max = hrt.dx_dy_between_rasters(meta_big=self.lu_raster.metadata, meta_small=self.depth_raster.metadata)

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
                                                pixel_factor=pixel_factor,
                                                calculation_type = calculation_type,
                                                )
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


    if True:
        #Variables
        cfg_file = r'../01_data/cfg/cfg_hhnk_2020.cfg'
        landuse_file = r'../01_data/landuse2020_tiles/combined_rasters.vrt'

        depth_file = r'../01_data/marken_rev23_max_depth_blok_GGG_T10.tif'
        output_file = r'../01_data/marken_rev23_damage_blok_GGG_T10.tif'


        wss_settings = {'inundation_period': 48, #uren
                        'herstelperiode':'10 dagen',
                        'maand':'sep',
                        'cfg_file':cfg_file,
                        'dmg_type':'gem'}
        
        # out_format = ["sum", "direct", "indirect"] 

        #Calculation
        self = Waterschadeschatter(depth_file=depth_file, 
                                landuse_file=landuse_file, 
                                wss_settings=wss_settings,
                                )

        # Berkenen schaderaster
        self.run(output_raster=hrt.Raster(output_file), 
            calculation_type="sum", 
            verbose=True, 
            overwrite=False,
            )
