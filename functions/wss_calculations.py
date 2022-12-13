import numpy as np

DMG_NODATA = 0 #let op staat dubbel, ook in wss_main.


def calculate_damage(caller, lu_block, depth_block, indices, dmg_table_landuse, dmg_table_general, pixel_factor):
    #GAMMA DEPTH CALCULATION

    #Interpoleren van het diepteraster en de gamma array.
    ysize, xsize = depth_block.shape
    k, j = np.meshgrid(np.arange(xsize), np.arange(ysize))

    xp=np.array(dmg_table_general['inundatiediepte'])

    #Zoek voor de diepte_array de dichtst bijliggende index wanneer vergeleken met xp.
    #Ookal gaat dit 'links', we willen de index hebben daarom krijg index_onder -1
    depth_block=np.round(depth_block,2) #FIXME Stowa WSS rond af op 2 decimalen. 
    depth_mask = depth_block==caller.depth_raster.nodata

    index_boven = np.searchsorted(xp, depth_block, side='left')
    index_boven[depth_mask] = 1 #Tijdelijke oplossing om de berekening wel te kunnen maken. Gamma_inundatiediepte worden later voor dit masker ook op 0 gezet.

    index_onder=index_boven.copy()-1

    #Stacked array zijn de gamma waarden van de inundatiediepte. Heeft dezelfde vorm als depth_block.
    # En dan x lagen gelijk aan len(xp) 
    stacked_array = []
    for i_depth in range(len(xp)):
            lookup = np.asarray([dmg_table_landuse[i].gamma_inundatiediepte[i_depth] for i in range(0,255)])
            stacked_array.append(lookup[lu_block]) # Max directe schade.
        # stacked_array.append(np.take(lookup, lu_block))
    stacked_array = np.stack(stacked_array)

    #Met de index arrays kunnen we nu de onder en bovenwaarde ophalen om vervolgens linear te interpoleren
    #Bijkomend mag de geinterpoleerde waarde niet groter of kleiner zijn dan xp[-1]
    #Dat wordt bereikt door in wss_loading de cfg waarden voor en achter aan te vullen. 

    #gamma_inundatiediepte = (y2-y1)/(x2-x1) * (x-x1) + y1
    np.seterr(invalid='ignore') #Delen door 0 is niet te voorkomen. Met het mask berekenen we de waarden hier.
    mask = index_onder==index_boven #dy/dx is hier 0, we nemen dan de gamma_inundatiediepte met de onderste index .
    y1=stacked_array[index_onder, j, k]
    y2=stacked_array[index_boven, j, k]
    gamma_inundatiediepte = (np.divide((y2 - y1), (xp[index_boven] - xp[index_onder]))) * (depth_block-xp[index_onder]) + y1

    gamma_inundatiediepte[mask] = y1[mask]
    gamma_inundatiediepte[depth_mask] = np.nan

    #Indirecte schade telt alleen bij inundatiediepte >0
    mask_indirect = depth_block<=0

    #For debugging.
    caller.gamma_inundatiediepte = gamma_inundatiediepte

    #DAMAGE CALCULATION

    #Apply lookup table. Change the landuse with direct damage.
    def calculate_damage_direct(i):
        """schade = max. directe schade · γdiepte · γduur · γseizoen + indirecte schade per dag · hersteltijd"""
        lu = dmg_table_landuse[i]
        return lu.direct * lu.gamma_inundatieduur_interp * lu.gamma_maand[indices['maand']] * lu.direct_eenheid_factor

    def calculate_damage_indirect(i):
        #TODO hoe werkt inundatiediepte door op indirecte schade?
        """schade = max. directe schade · γdiepte · γduur · γseizoen + indirecte schade per dag · hersteltijd"""
        lu = dmg_table_landuse[i]
        return lu.indirect * lu.gamma_herstelperiode[indices['herstelperiode']] * lu.indirect_eenheid_factor

    # Create lookuptable. Landuse value will be replaced by calculated damage. 
    lookup_direct = np.asarray([calculate_damage_direct(i) for i in range(0,255)])
    lookup_indirect =  np.asarray([calculate_damage_indirect(i) for i in range(0,255)])

    # Max directe schade.
    damage_direct = lookup_direct[lu_block] #same as np.take(lookup_direct, lu_block), .take seems slower.
    damage_indirect = lookup_indirect[lu_block]
    damage_indirect[mask_indirect] = DMG_NODATA

    # Damage
    #schade = max. directe schade · γdiepte · γduur · γseizoen + indirecte schade per dag · hersteltijd
    # damage is per m2. Multiply by pixelfactor to get damage per pixel.
    return (damage_direct * gamma_inundatiediepte + damage_indirect) * pixel_factor
