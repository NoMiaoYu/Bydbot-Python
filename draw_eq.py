import asyncio
import logging
import matplotlib
matplotlib.use('Agg')  # 非交互式后端
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from matplotlib.patches import FancyBboxPatch
import tempfile
import numpy as np
import os


# 全局配置
plt.rcParams['font.sans-serif'] = ['Minecraft AE']
plt.rcParams['axes.unicode_minus'] = False
plt.ioff()


async def draw_earthquake_async(data, source=None):
    """异步绘制地震地图"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, draw_earthquake, data, source)


def draw_earthquake(data, source=None):
    """绘制地震地图的主要函数"""
    try:
        # 提取地震数据
        lat = float(data['latitude'])
        lon = float(data['longitude'])
        mag = float(data['magnitude'])
        time = data.get('shockTime', '未知时间')
        place = data.get('placeName', '未知地点')
        info_type = data.get('infoTypeName', '')

        # 计算地图范围
        map_extent = calculate_map_extent(lon, lat)
        lon_min, lon_max, lat_min, lat_max = map_extent

        # 获取数据源信息（如果存在）
        data_source = data.get('_source', source)

        # 创建地图图像
        temp_map_path = create_map_image(lat, lon, map_extent, lon_min, lon_max, lat_min, lat_max, data_source)

        # 在地图上添加信息框
        final_image_path = add_info_box_to_image(temp_map_path, time, place, info_type, mag, lon, lat, data_source)

        # 清理临时文件
        if os.path.exists(temp_map_path):
            os.remove(temp_map_path)

        logging.info(f"地震地图绘制成功：{final_image_path}")
        return final_image_path

    except Exception as e:
        logging.error(f"绘图失败：{str(e)}", exc_info=True)
        plt.close('all')
        return None


def calculate_map_extent(lon, lat):
    """计算地图范围"""
    extent_size_lon = 0.9  # 缩小视野以显示震源周围更多详细情况（原值1.0，现在放大0.1）
    extent_size_lat = 0.9 if abs(lat) < 60 else 1.35  # 考虑高纬度地区，相应缩小（原值1.0/1.5，现在放大0.1）
    lon_min, lon_max = lon - extent_size_lon, lon + extent_size_lon
    lat_min, lat_max = lat - extent_size_lat, lat + extent_size_lat

    return lon_min, lon_max, lat_min, lat_max


def create_map_image(lat, lon, map_extent, lon_min, lon_max, lat_min, lat_max, data_source=None):
    """创建基础地图图像"""
    # 固定画布尺寸 1200x900 像素
    target_width_px, target_height_px = 1200, 900
    dpi = 180

    # 为了防止黑边，我们先创建一个稍大的画布，然后裁剪到目标尺寸
    # 计算纵横比
    aspect_ratio = (lon_max - lon_min) / (lat_max - lat_min)
    target_width_inches = target_width_px / dpi
    target_height_inches = target_height_px / dpi

    # 计算画布尺寸
    calc_width_inches = target_height_inches * aspect_ratio
    calc_height_inches = target_width_inches / aspect_ratio

    if calc_width_inches >= target_width_inches and calc_height_inches >= target_height_inches:
        fig_width = calc_width_inches
        fig_height = target_height_inches
    elif calc_width_inches < target_width_inches:
        fig_width = target_width_inches
        fig_height = target_width_inches / aspect_ratio
    else:
        fig_height = target_height_inches
        fig_width = target_height_inches * aspect_ratio

    # 为了防止黑边，稍微增加画布尺寸
    scale_factor = 1.1  # 增加10%的画布尺寸
    fig_width *= scale_factor
    fig_height *= scale_factor

    # 绘制地图主体
    fig_map = plt.figure(figsize=(fig_width, fig_height), facecolor='black', dpi=dpi)
    ax_map = plt.axes(projection=ccrs.PlateCarree(central_longitude=lon), frameon=False)
    # 使用精确的地图范围，不添加额外边距
    ax_map.set_extent([lon_min, lon_max, lat_min, lat_max], crs=ccrs.PlateCarree())

    # 设置地图特征
    set_map_features(ax_map, lon_min, lon_max, lat_min, lat_max, lat, lon, data_source)

    # 添加震中标记
    add_earthquake_marker(ax_map, lon, lat)

    # 设置轴属性
    ax_map.set_axis_off()
    ax_map.patch.set_visible(False)
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)

    # 保存临时地图图像
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_map:
        plt.savefig(
            tmp_map.name,
            bbox_inches='tight',  # 使用tight边界以确保完全填充
            pad_inches=0,         # 无内边距
            facecolor='black',
            edgecolor='black',
            dpi=dpi
        )
        plt.close(fig_map)
        return tmp_map.name


def set_map_features(ax_map, lon_min, lon_max, lat_min, lat_max, lat, lon, data_source=None):
    """设置地图特征，包括陆地、海洋、边界等"""
    ax_map.margins(0)

    # 添加地图特征
    ax_map.add_feature(cfeature.OCEAN, facecolor="#1f2323")
    ax_map.add_feature(cfeature.LAND, facecolor="#3d4141")
    ax_map.add_feature(cfeature.COASTLINE, edgecolor='white', linewidth=0.5)
    ax_map.add_feature(cfeature.LAKES, facecolor='#1f2323', edgecolor='white', linewidth=0.3)
    ax_map.add_feature(cfeature.RIVERS, edgecolor='white', linewidth=0.3, alpha=0.5)
    ax_map.add_feature(cfeature.BORDERS, edgecolor='white', linewidth=0.4, linestyle='--')
    ax_map.add_feature(cfeature.STATES, linewidth=0.3, edgecolor='gray', facecolor='none', alpha=0.5)

    # 只有cenc、cea和cea-pr数据源才绘制中国断层
    if data_source in ['cenc', 'cea', 'cea-pr']:
        draw_china_faults(ax_map, lon_min, lon_max, lat_min, lat_max)


def draw_china_faults(ax_map, lon_min, lon_max, lat_min, lat_max):
    """绘制中国断层数据"""
    try:
        gmt_file_path = os.path.join(os.path.dirname(__file__), 'data', 'CN-faults.gmt')
        if os.path.exists(gmt_file_path):
            with open(gmt_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            current_fault = []
            for line in lines:
                line = line.strip()
                if line.startswith('>'):
                    # 绘制当前断层数据
                    if current_fault:
                        lons, lats = zip(*current_fault)
                        ax_map.plot(lons, lats, color='black', linewidth=0.5, alpha=0.6, transform=ccrs.PlateCarree())
                    current_fault = []
                elif line and not line.startswith('#'):
                    # 解析坐标数据
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            lon_val = float(parts[0])
                            lat_val = float(parts[1])
                            # 只绘制在当前视图范围内的断层
                            if lon_min <= lon_val <= lon_max and lat_min <= lat_val <= lat_max:
                                current_fault.append((lon_val, lat_val))
                        except ValueError:
                            continue

            # 绘制最后一组断层数据
            if current_fault:
                lons, lats = zip(*current_fault)
                ax_map.plot(lons, lats, color='black', linewidth=0.5, alpha=0.6, transform=ccrs.PlateCarree())
    except Exception as e:
        logging.error(f"加载断层数据时出错: {e}")


def add_earthquake_marker(ax_map, lon, lat):
    """添加地震震中标记"""
    # 由于地图视野缩小，震中标记也需要相应缩小
    # 白色外层描边 - 从左上到右下
    ax_map.plot([lon-0.025, lon+0.025], [lat+0.025, lat-0.025], color='white', linewidth=6, transform=ccrs.PlateCarree(), zorder=3)
    # 白色外层描边 - 从右上到左下
    ax_map.plot([lon+0.025, lon-0.025], [lat+0.025, lat-0.025], color='white', linewidth=6, transform=ccrs.PlateCarree(), zorder=3)
    # 红色交叉主体 - 从左上到右下
    ax_map.plot([lon-0.02, lon+0.02], [lat+0.02, lat-0.02], color='#FF0000', linewidth=3, transform=ccrs.PlateCarree(), zorder=4)
    # 红色交叉主体 - 从右上到左下
    ax_map.plot([lon+0.02, lon-0.02], [lat+0.02, lat-0.02], color='#FF0000', linewidth=3, transform=ccrs.PlateCarree(), zorder=4)


def add_info_box_to_image(temp_map_path, time, place, info_type, mag, lon, lat, source=None):
    """在地图图像上添加信息框"""
    # 读取临时图像
    img = plt.imread(temp_map_path)
    h, w = img.shape[:2]

    # 目标尺寸
    target_width_px, target_height_px = 1200, 900

    # 如果当前图像尺寸小于目标尺寸，则扩展图像
    img = ensure_minimum_size(img, target_width_px, target_height_px, h, w)

    # 从中心裁剪到目标尺寸
    img_cropped = crop_image(img, target_width_px, target_height_px)

    # 创建最终画布
    dpi = 180
    fig_width_inches = target_width_px / dpi
    fig_height_inches = target_height_px / dpi
    fig_final = plt.figure(figsize=(fig_width_inches, fig_height_inches), dpi=dpi, facecolor='black')
    ax_final = fig_final.add_axes([0, 0, 1, 1], frameon=False)
    ax_final.imshow(img_cropped, aspect='auto')
    ax_final.set_xlim(0, img_cropped.shape[1])
    ax_final.set_ylim(img_cropped.shape[0], 0)
    ax_final.set_axis_off()
    ax_final.margins(0)
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)

    # 添加信息框
    add_info_text(ax_final, time, place, info_type, mag, lon, lat)

    # 保存最终图像到自定义目录
    if source:
        # 创建 pictures/{source} 目录
        pictures_dir = os.path.join(os.path.dirname(__file__), 'pictures', source)
        os.makedirs(pictures_dir, exist_ok=True)
        
        # 生成唯一的文件名
        import time as time_module
        timestamp = int(time_module.time() * 1000)
        filename = f"eq_{timestamp}.png"
        final_path = os.path.join(pictures_dir, filename)
    else:
        # 使用临时文件（向后兼容）
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_final:
            final_path = tmp_final.name

    plt.savefig(
        final_path,
        bbox_inches=0,
        facecolor='black',
        dpi=dpi
    )
    plt.close(fig_final)
    return final_path


def ensure_minimum_size(img, target_width_px, target_height_px, h, w):
    """确保图像至少达到目标尺寸"""
    if w < target_width_px or h < target_height_px:
        # 计算需要扩展的像素
        dw = max(0, target_width_px - w)
        dh = max(0, target_height_px - h)

        # 扩展图像
        new_img = np.zeros((max(h, target_height_px), max(w, target_width_px), img.shape[2]), dtype=img.dtype)
        new_img[:h, :w] = img

        # 如果需要扩展宽度，在右侧扩展
        if dw > 0:
            for i in range(dw):
                new_img[:, w + i] = new_img[:, w - 1]

        # 如果需要扩展高度，在底部扩展
        if dh > 0:
            for i in range(dh):
                new_img[h + i, :] = new_img[h - 1, :]

        img = new_img
    return img


def crop_image(img, target_width_px, target_height_px):
    """从图像中心裁剪到目标尺寸"""
    h, w = img.shape[:2]
    start_h = max(0, (h - target_height_px) // 2)
    start_w = max(0, (w - target_width_px) // 2)
    end_h = min(h, start_h + target_height_px)
    end_w = min(w, start_w + target_width_px)

    # 确保裁剪区域正好是目标尺寸
    img_cropped = img[start_h:end_h, start_w:end_w]

    # 如果裁剪后的图像仍小于目标尺寸，在右侧和底部填充
    ch, cw = img_cropped.shape[:2]
    if cw < target_width_px or ch < target_height_px:
        padded_img = np.zeros((target_height_px, target_width_px, img_cropped.shape[2]), dtype=img_cropped.dtype)
        padded_img[:ch, :cw] = img_cropped
        # 填充右侧
        if cw < target_width_px:
            for i in range(cw, target_width_px):
                padded_img[:ch, i] = padded_img[:ch, cw-1]
        # 填充底部
        if ch < target_height_px:
            for i in range(ch, target_height_px):
                padded_img[i, :target_width_px] = padded_img[ch-1, :target_width_px]
        img_cropped = padded_img

    return img_cropped


def add_info_text(ax_final, time, place, info_type, mag, lon, lat):
    """添加地震信息文本和框"""
    # 格式化经纬度为带方向的形式
    lon_direction = "E" if lon >= 0 else "W"
    lat_direction = "N" if lat >= 0 else "S"
    formatted_lon = f"{abs(lon):.2f}°{lon_direction}"
    formatted_lat = f"{abs(lat):.2f}°{lat_direction}"
    
    info_text = f"{time} {place}[{info_type}] M{mag:.1f}"
    
    # 计算字体大小
    font_size = calculate_font_size(info_text)
    
    # 使用 figure 的坐标系来添加文本框
    fig = ax_final.get_figure()
    
    # 计算文本框宽度
    bbox_width = calculate_textbox_width(fig, info_text, font_size)
    bbox_height = 0.04  # 文本框高度

    # 添加文本框背景
    from matplotlib.patches import FancyBboxPatch
    bbox = FancyBboxPatch(
        (0.01, 0.92),
        bbox_width, bbox_height,
        boxstyle="round,pad=0.01",
        fc="white", ec="none",
        transform=fig.transFigure,  # 使用 figure 的坐标系
        alpha=0.95
    )
    fig.patches.append(bbox)

    # 添加文本
    fig.text(
        0.015, 0.92 + bbox_height / 2,
        info_text,
        fontsize=font_size,
        color='black',
        va='center', ha='left',
        transform=fig.transFigure,  # 使用 figure 的坐标系
        weight='bold',
        antialiased=True
    )


def calculate_font_size(info_text):
    """根据文本长度计算合适的字体大小"""
    text_length = len(info_text)
    base_font_size = 14
    if text_length > 20:
        font_size = base_font_size * (20 / text_length)
    elif text_length < 10:
        font_size = base_font_size * 1.2
    else:
        font_size = base_font_size
    return max(10, min(16, font_size))  # 限制字体大小范围


def calculate_textbox_width(fig, info_text, font_size):
    """计算文本框宽度"""
    try:
        # 使用TextPath来精确测量文本宽度
        from matplotlib.textpath import TextPath
        from matplotlib.font_manager import FontProperties

        # 获取字体属性
        font_props = FontProperties()
        font_props.set_family(['Minecraft AE'])

        # 创建文本路径来测量实际文本宽度
        tp = TextPath((0, 0), info_text, size=font_size, prop=font_props)
        # 获取文本边界框的宽度
        text_bbox = tp.get_extents()
        text_width_points = text_bbox.width

        # 转换为相对于图形的宽度估算
        estimated_text_width_ratio = text_width_points / (fig.get_figwidth() * 72)  # 72 points per inch

        # 为了确保文本框足够宽，增加一些边距
        padding_ratio = 0.05  # 5%的额外空间
        calculated_text_box_width = min(0.8, estimated_text_width_ratio + padding_ratio)

        # 确保文本框最小宽度
        return max(0.2, calculated_text_box_width)
    except:
        # 如果无法精确计算，使用默认宽度
        return 0.4