import configparser
import numpy as np

def read_dmg_table_config(wss_settings) -> dict:
    """Read damagetable. Returns dictionary with keys corresponding to the 
    landuse index. """

    class Landuse_damagetable():
        """Damagetable for one land use"""
        def __init__(self, section):
            """Section is part of the configparser. [i.items(sect) for i in parser.sections()]"""
            self.section = dict(section)
            for key in self.section:
                if '[' in self.section[key]:
                    setattr(self, key, eval(self.section[key]))
                else:
                    try:
                        setattr(self, key, int(self.section[key]))
                    except:
                        setattr(self, key, self.section[key])

            #Omrekenen van eenheden.
            if self.direct_eenheid == '/ha': 
                self.direct_eenheid_factor = 1/10000
            elif self.direct_eenheid == '/m2':
                self.direct_eenheid_factor = 1
            if self.indirect_eenheid == '/m2/dag':
                self.indirect_eenheid_factor = 1
        

            x=wss_settings['duur_uur']
            xp=dmg_table_general['inundatieduur']
            fp=self.gamma_inundatieduur

            self.gamma_inundatieduur_interp = np.interp(x=x, xp=xp, fp=fp)


        def __repr__(self):
            return f"""{self.omschrijving}"""

    parser = configparser.ConfigParser()
    parser.read(filenames=wss_settings['cfg_file'])

    dmg_table_landuse={}

    #Read file
    #Create general table
    for sect in parser.sections():
        if sect =='algemeen':
            dmg_table_general = dict(parser.items(sect))
            for key in dmg_table_general: #List in string to list.
                dmg_table_general[key] = eval(dmg_table_general[key])
            break

    #create table per landuse
    for sect in parser.sections():
        if sect !='algemeen':
            dmg_table_landuse[int(sect)] = Landuse_damagetable(parser.items(sect))


    #Fill missing values with dummy values. Dummy is defined as landuse=0
    for i in range(0,255): #Careful. Landuse value should be max 254
        if i not in dmg_table_landuse:
            dmg_table_landuse[i] = dmg_table_landuse[0]

    return dmg_table_landuse, dmg_table_general

