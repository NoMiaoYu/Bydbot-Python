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

# 全局配置
plt.rcParams['font.sans-serif'] = ['Minecraft AE']
plt.rcParams['axes.unicode_minus'] = False
plt.ioff()

async def draw_earthquake_async(data):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, draw_earthquake, data)

def draw_earthquake(data):
    try:
        # 1. 提取数据
        lat = float(data['latitude'])
        lon = float(data['longitude'])
        mag = float(data['magnitude'])
        time = data.get('shockTime', '未知时间')
        place = data.get('placeName', '未知地点')
        info_type = data.get('infoTypeName', '')

        # 2. 计算地图范围
        extent_size_lon = 12
        extent_size_lat = 10 if abs(lat) < 60 else 12
        lon_min, lon_max = lon - extent_size_lon, lon + extent_size_lon
        lat_min, lat_max = lat - extent_size_lat, lat + extent_size_lat

        # 3. 画布尺寸 - 修改为固定1200x900像素
        target_width_px, target_height_px = 1200, 900
        dpi = 180  # 保持高分辨率

        # 计算纵横比
        aspect_ratio = (lon_max - lon_min) / (lat_max - lat_min)

        # 计算以英寸为单位的尺寸，确保至少达到目标像素数
        target_width_inches = target_width_px / dpi
        target_height_inches = target_height_px / dpi

        # 如果按比例计算的尺寸小于目标尺寸，则扩展较小的一边
        calc_width_inches = target_height_inches * aspect_ratio
        calc_height_inches = target_width_inches / aspect_ratio

        if calc_width_inches >= target_width_inches and calc_height_inches >= target_height_inches:
            # 当前计算的尺寸已经满足要求
            fig_width = calc_width_inches
            fig_height = target_height_inches
        elif calc_width_inches < target_width_inches:
            # 宽度不够，使用目标宽度并相应调整高度
            fig_width = target_width_inches
            fig_height = target_width_inches / aspect_ratio
        else:
            # 高度不够，使用目标高度并相应调整宽度
            fig_height = target_height_inches
            fig_width = target_height_inches * aspect_ratio

        # 4. 第一步：绘制地图主体（无信息框）
        fig_map = plt.figure(figsize=(fig_width, fig_height), facecolor='black', dpi=dpi)
        ax_map = plt.axes(projection=ccrs.PlateCarree(central_longitude=lon), frameon=False)
        ax_map.set_extent([lon_min - 0.5, lon_max + 0.5, lat_min - 0.5, lat_max + 0.5], crs=ccrs.PlateCarree())

        # 确保地图填满整个轴，移除任何空白边距
        ax_map.margins(0)

        # 【修改1：海洋和湖泊改为黑色】
        ax_map.add_feature(cfeature.OCEAN, facecolor="#1f2323")
        ax_map.add_feature(cfeature.LAND, facecolor="#3d4141")
        ax_map.add_feature(cfeature.COASTLINE, edgecolor='white', linewidth=0.5)
        ax_map.add_feature(cfeature.LAKES, facecolor='#1f2323', edgecolor='white', linewidth=0.3)
        ax_map.add_feature(cfeature.RIVERS, edgecolor='white', linewidth=0.3, alpha=0.5)
        ax_map.add_feature(cfeature.BORDERS, edgecolor='white', linewidth=0.4, linestyle='--')

        # 震中标记 - 使用两条对角线形成 ❌ 形状，白色描边
        # 白色外层描边 - 从左上到右下
        ax_map.plot([lon-0.35, lon+0.35], [lat+0.35, lat-0.35], color='white', linewidth=6, transform=ccrs.PlateCarree(), zorder=3)
        # 白色外层描边 - 从右上到左下
        ax_map.plot([lon+0.35, lon-0.35], [lat+0.35, lat-0.35], color='white', linewidth=6, transform=ccrs.PlateCarree(), zorder=3)
        # 红色交叉主体 - 从左上到右下
        ax_map.plot([lon-0.32, lon+0.32], [lat+0.32, lat-0.32], color='#FF0000', linewidth=3, transform=ccrs.PlateCarree(), zorder=4)
        # 红色交叉主体 - 从右上到左下
        ax_map.plot([lon+0.32, lon-0.32], [lat+0.32, lat-0.32], color='#FF0000', linewidth=3, transform=ccrs.PlateCarree(), zorder=4)

        ax_map.set_axis_off()
        ax_map.patch.set_visible(False)

        # 设置子图参数，确保地图填满整个画布
        plt.subplots_adjust(left=0, right=1, top=1, bottom=0)

        # 保存临时地图图像（仅地图，无信息框）
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_map:
            plt.savefig(
                tmp_map.name,
                bbox_inches=0,  # 使用精确边界，不添加额外边距
                facecolor='black',
                edgecolor='black',  # 确保边缘也是黑色
                dpi=dpi
            )
            plt.close(fig_map)

        # 5. 第二步：加载地图图像并添加信息框
        # 读取临时图像
        img = plt.imread(tmp_map.name)
        h, w = img.shape[:2]

        # 目标尺寸
        target_width_px, target_height_px = 1200, 900

        # 如果当前图像尺寸小于目标尺寸，则扩展图像以避免黑边
        if w < target_width_px or h < target_height_px:
            # 计算需要扩展的像素
            dw = max(0, target_width_px - w)
            dh = max(0, target_height_px - h)

            # 扩展图像
            new_img = np.zeros((max(h, target_height_px), max(w, target_width_px), img.shape[2]), dtype=img.dtype)
            new_img[:h, :w] = img

            # 如果需要扩展宽度，在右侧扩展
            if dw > 0:
                # 复制最右边的列进行填充
                for i in range(dw):
                    new_img[:, w + i] = new_img[:, w - 1]

            # 如果需要扩展高度，在底部扩展
            if dh > 0:
                # 复制最下面的行进行填充
                for i in range(dh):
                    new_img[h + i, :] = new_img[h - 1, :]

            img = new_img
            h, w = img.shape[:2]

        # 从中心裁剪到目标尺寸，如果图像过大
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

        # 创建最终画布 - 固定为1200x900像素
        dpi = 180
        fig_width_inches = target_width_px / dpi
        fig_height_inches = target_height_px / dpi
        fig_final = plt.figure(figsize=(fig_width_inches, fig_height_inches), dpi=dpi, facecolor='black')
        ax_final = fig_final.add_axes([0, 0, 1, 1], frameon=False)  # 确保没有框架
        ax_final.imshow(img_cropped, aspect='auto')  # 确保图像自动适应整个轴
        ax_final.set_xlim(0, img_cropped.shape[1])  # 明确设置x轴范围
        ax_final.set_ylim(img_cropped.shape[0], 0)  # 明确设置y轴范围（翻转以匹配图像坐标）
        ax_final.set_axis_off()

        # 确保图像填满整个轴
        ax_final.margins(0)
        plt.subplots_adjust(left=0, right=1, top=1, bottom=0)

        # 添加信息框
        # 格式化经纬度为带方向的形式（保留此代码供其他用途）
        lon_direction = "E" if lon >= 0 else "W"
        lat_direction = "N" if lat >= 0 else "S"
        formatted_lon = f"{abs(lon):.2f}°{lon_direction}"
        formatted_lat = f"{abs(lat):.2f}°{lat_direction}"
        info_text = f"{time} {place}[{info_type}] M{mag:.1f}"
        text_length = len(info_text)
        base_font_size = 14  # 恢复基础字体大小
        if text_length > 20:
            font_size = base_font_size * (20 / text_length)
        elif text_length < 10:
            font_size = base_font_size * 1.2
        else:
            font_size = base_font_size
        font_size = max(10, min(16, font_size))  # 调整字体大小范围

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

        # 转换为相对于图形的宽度 (大约估算)
        # 由于matplotlib坐标系的复杂性，我们使用一个估算方法
        estimated_text_width_ratio = text_width_points / (fig_final.get_figwidth() * 72)  # 72 points per inch

        # 为了确保文本框足够宽，增加一些边距
        padding_ratio = 0.05  # 5%的额外空间
        calculated_text_box_width = min(0.8, estimated_text_width_ratio + padding_ratio)

        # 确保文本框最小宽度
        bbox_width = max(0.2, calculated_text_box_width)
        bbox_height = 0.04  # 减小文本框高度

        bbox = FancyBboxPatch(
            (0.01, 0.92),
            bbox_width, bbox_height,
            boxstyle="round,pad=0.01",
            fc="white", ec="none",
            transform=fig_final.transFigure,
            alpha=0.95
        )
        fig_final.patches.append(bbox)

        fig_final.text(
            0.015, 0.92 + bbox_height / 2,  # 调整垂直位置以在文本框中居中
            info_text,
            fontsize=font_size,
            color='black',
            va='center', ha='left',  # 垂直居中，水平左对齐
            transform=fig_final.transFigure,
            weight='bold',
            antialiased=True
        )

        # 保存最终图像
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_final:
            plt.savefig(
                tmp_final.name,
                bbox_inches=0,  # 使用精确边界，不添加额外边距
                facecolor='black',
                dpi=dpi
            )
            plt.close(fig_final)
            logging.info(f"地震地图绘制成功：{tmp_final.name}")
            return tmp_final.name

    except Exception as e:
        logging.error(f"绘图失败：{str(e)}", exc_info=True)
        plt.close('all')
        return None