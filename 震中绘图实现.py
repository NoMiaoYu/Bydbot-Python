import matplotlib.pyplot as plt

def plot_epicenter_marker(
    lon, 
    lat, 
    marker_size=28, 
    inner_color='red', 
    edge_color='white', 
    edge_width=3,
    background_color='#222222',
    title='Epicenter Marker',
    save_path=None
):
    """
    极简修改版：仅调整白色叉号的marker_size，保留你喜欢的原版样式
    核心：白色外层比红色内层大2个单位（像素级），四角完全闭合
    """
    # 创建绘图窗口
    plt.figure(figsize=(8, 6))
    
    # 核心修改：白色外层marker_size = 红色内层 + 2（仅改这一个参数）
    # 外层白色描边（臂长多2个像素）
    plt.plot(
        lon, lat,
        marker='x',
        color=edge_color,
        markersize=marker_size + 2,  # 仅这里+2，加长白色叉号的臂
        markeredgewidth=edge_width + 4,
        linestyle='None'
    )
    # 内层红色主体（保持你喜欢的原有尺寸）
    plt.plot(
        lon, lat,
        marker='x',
        color=inner_color,
        markersize=marker_size,      # 完全保留你喜欢的尺寸
        markeredgewidth=edge_width + 1,
        linestyle='None'
    )
    
    # 以下代码完全保留你喜欢的原版配置，一字不改
    plt.xlabel('Longitude (°)', fontsize=12, color='white')
    plt.ylabel('Latitude (°)', fontsize=12, color='white')
    plt.title(title, fontsize=14, fontweight='bold', color='white')
    
    ax = plt.gca()
    ax.set_facecolor(background_color)
    ax.tick_params(colors='white')
    for spine in ax.spines.values():
        spine.set_color('white')
    
    plt.xlim(lon-2, lon+2)
    plt.ylim(lat-2, lat+2)
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"图片已保存至: {save_path}")
    
    plt.show()

# ------------------- 保留你喜欢的调用方式 -------------------
if __name__ == "__main__":
    plot_epicenter_marker(
        lon=104.0,          
        lat=30.0,           
        marker_size=28,     # 你喜欢的原有尺寸
        inner_color='red',  
        edge_color='white', 
        edge_width=3,       # 你喜欢的原有宽度
        title='Earthquake Epicenter'
        # save_path='./epicenter_marker.png'
    )