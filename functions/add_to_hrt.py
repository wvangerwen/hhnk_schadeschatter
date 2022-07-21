def dx_dy_between_rasters(meta_big, meta_small):
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