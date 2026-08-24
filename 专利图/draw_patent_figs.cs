using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.IO;

// 生成专利合规的黑白线条流程图（图1 整体流程图、图4 S3联合优化流程图）
class PatentFigs
{
    static Font fBox, fTitle, fSmall;
    static Pen solid, dash, thin;
    static Brush black, white;

    static void Init(Graphics g)
    {
        g.SmoothingMode = SmoothingMode.AntiAlias;
        g.TextRenderingHint = System.Drawing.Text.TextRenderingHint.AntiAlias;
        fBox = new Font("SimSun", 25f, FontStyle.Regular, GraphicsUnit.Pixel);
        fTitle = new Font("SimHei", 30f, FontStyle.Bold, GraphicsUnit.Pixel);
        fSmall = new Font("SimSun", 20f, FontStyle.Regular, GraphicsUnit.Pixel);
        solid = new Pen(Color.Black, 2.5f);
        thin = new Pen(Color.Black, 1.8f);
        dash = new Pen(Color.Black, 2.2f); dash.DashStyle = DashStyle.Dash;
        black = Brushes.Black; white = Brushes.White;
    }

    static StringFormat Center()
    {
        StringFormat sf = new StringFormat();
        sf.Alignment = StringAlignment.Center;
        sf.LineAlignment = StringAlignment.Center;
        return sf;
    }

    static void Box(Graphics g, float x, float y, float w, float h, string text, Pen border, Font f)
    {
        g.FillRectangle(white, x, y, w, h);
        g.DrawRectangle(border, x, y, w, h);
        g.DrawString(text, f, black, new RectangleF(x + 6, y, w - 12, h), Center());
    }

    static void Diamond(Graphics g, float cx, float cy, float w, float h, string text)
    {
        PointF[] p = new PointF[] {
            new PointF(cx, cy - h/2), new PointF(cx + w/2, cy),
            new PointF(cx, cy + h/2), new PointF(cx - w/2, cy) };
        g.FillPolygon(white, p);
        g.DrawPolygon(solid, p);
        g.DrawString(text, fBox, black, new RectangleF(cx - w/2 + 10, cy - h/2, w - 20, h), Center());
    }

    static void Arrow(Graphics g, Pen p, float x1, float y1, float x2, float y2)
    {
        Pen ap = (Pen)p.Clone();
        ap.CustomEndCap = new AdjustableArrowCap(6, 7);
        g.DrawLine(ap, x1, y1, x2, y2);
        ap.Dispose();
    }

    static void Label(Graphics g, string s, float x, float y)
    {
        g.DrawString(s, fSmall, black, x, y);
    }

    // ---------------- 图1 整体流程图 ----------------
    static void DrawFig1(string path)
    {
        int W = 1500, H = 1180;
        Bitmap bmp = new Bitmap(W, H);
        bmp.SetResolution(300f, 300f);
        Graphics g = Graphics.FromImage(bmp);
        Init(g);
        g.Clear(Color.White);

        float bx = 210, bw = 1080, cx = bx + bw / 2;
        Box(g, bx, 55, bw, 80, "获取声呐图像序列与时间戳对齐的里程计数据", solid, fBox);
        Arrow(g, solid, cx, 135, cx, 195);
        Box(g, bx, 195, bw, 120, "S1  多源数据同步获取与声学投影初始化", solid, fBox);
        Arrow(g, solid, cx, 315, cx, 375);
        Label(g, "二维观测特征点集 / 初始粗位姿轨迹", bx + bw + 8, 325);
        Box(g, bx, 375, bw, 120, "S2  声学软数据关联构建与相对球坐标映射", solid, fBox);
        Arrow(g, solid, cx, 495, cx, 555);
        Label(g, "全局特征关联图 / 相对球坐标初始地标", bx + bw + 8, 505);
        Box(g, bx, 555, bw, 140, "S3  视场边界约束下的位姿与置信度权重联合优化", solid, fBox);
        Arrow(g, solid, cx, 695, cx, 755);
        Label(g, "高精度位姿 / 收敛置信度权重 / 优化地标", bx + bw + 8, 705);
        Box(g, bx, 755, bw, 140, "S4  污染数据剔除与全局三维曲面重建", solid, fBox);
        Arrow(g, solid, cx, 895, cx, 955);
        Box(g, bx, 955, bw, 80, "输出水下目标三维曲面网格模型", solid, fBox);

        g.DrawString("图1  本发明方法的整体流程图", fTitle, black,
            new RectangleF(0, 1085, W, 50), Center());

        Save(bmp, g, path);
    }

    // ---------------- 图4 S3联合优化流程图 ----------------
    static void DrawFig4(string path)
    {
        int W = 2000, H = 1500;
        Bitmap bmp = new Bitmap(W, H);
        bmp.SetResolution(300f, 300f);
        Graphics g = Graphics.FromImage(bmp);
        Init(g);
        g.Clear(Color.White);

        float bx = 360, bw = 1120, cx = bx + bw / 2;   // main column
        Box(g, bx, 55, bw, 100, "输入：初始粗位姿、相对球坐标初始地标、\n初始置信度权重、里程计相对运动增量", solid, fBox);
        Arrow(g, solid, cx, 155, cx, 210);
        Box(g, bx, 210, bw, 90, "S31  构建鲁棒联合优化代价函数（含 Huber 核）", solid, fBox);
        Arrow(g, solid, cx, 300, cx, 355);
        Box(g, bx, 355, bw, 100, "S32  提取声呐视场角与探测盲程，\n构建相对球坐标箱式硬约束集 Ω", solid, fBox);

        // 右侧优选分支：俯仰角可观测性自适应先验（虚线）
        float sx = 1520, sw = 430;
        Box(g, sx, 355, sw, 100, "优选：俯仰角可观测性\n自适应先验约束", dash, fSmall);
        Arrow(g, dash, bx + bw, 405, sx, 405);

        Arrow(g, solid, cx, 455, cx, 515);

        // 循环回路
        Box(g, bx, 515, bw, 95, "加权更新步：按残差更新置信度权重 w=w0·ψ(s)", solid, fBox);
        Arrow(g, solid, cx, 610, cx, 665);
        Box(g, bx, 665, bw, 95, "状态更新步：带边界约束信赖域反射(TRF)求解", solid, fBox);

        // 右侧优选：GNC 阈值调度（虚线）
        Box(g, sx, 560, sw, 100, "优选：鲁棒核阈值\n渐进调度（自大而小）", dash, fSmall);
        Arrow(g, dash, bx + bw, 610, sx, 610);

        Arrow(g, solid, cx, 760, cx, 820);
        // 判定菱形
        Diamond(g, cx, 900, 420, 170, "代价函数收敛？");
        // 否：回环（左侧虚线回到加权更新步）
        float lx = bx - 120;
        g.DrawLine(dash, cx - 210, 900, lx, 900);
        g.DrawLine(dash, lx, 900, lx, 562);
        Arrow(g, dash, lx, 562, bx, 562);
        Label(g, "否", lx + 10, 720);
        // 是：向下
        Arrow(g, solid, cx, 985, cx, 1045);
        Label(g, "是", cx + 12, 1000);
        Box(g, bx, 1045, bw, 100, "输出：高精度位姿轨迹、收敛置信度权重、\n优化三维地标集", solid, fBox);

        g.DrawString("图4  步骤S3 视场约束下位姿与置信度权重联合优化流程图", fTitle, black,
            new RectangleF(0, 1330, W, 50), Center());

        Save(bmp, g, path);
    }

    static void Node(Graphics g, float x, float y, float r)
    { g.FillEllipse(white, x - r, y - r, 2 * r, 2 * r); g.DrawEllipse(solid, x - r, y - r, 2 * r, 2 * r); }
    static void Dot(Graphics g, float x, float y, float r)
    { g.FillEllipse(black, x - r, y - r, 2 * r, 2 * r); }
    static void Txt(Graphics g, string s, float x, float y, Font f)
    { g.DrawString(s, f, black, x, y); }

    static void Triad(Graphics g, float ox, float oy, string sub, float len, bool bold)
    {
        Pen p = bold ? new Pen(Color.Black, 3.6f) : solid;
        Arrow(g, p, ox, oy, ox + len, oy);                 // X 轴 右（声轴/前向）
        Txt(g, "X" + sub, ox + len + 6, oy - 12, fSmall);
        Arrow(g, p, ox, oy, ox, oy - len);                 // Z 轴 上
        Txt(g, "Z" + sub, ox - 6, oy - len - 34, fSmall);
        Arrow(g, p, ox, oy, ox - 0.66f * len, oy - 0.66f * len); // Y 轴 左上（示意景深）
        Txt(g, "Y" + sub, ox - 0.66f * len - 44, oy - 0.66f * len - 22, fSmall);
        Node(g, ox, oy, 4);
        if (bold) p.Dispose();
    }

    // ---------------- 图2 声学空间投影模型与坐标系关系 ----------------
    static void DrawFig2(string path)
    {
        int W = 1900, H = 1200;
        Bitmap bmp = new Bitmap(W, H);
        bmp.SetResolution(300f, 300f);
        Graphics g = Graphics.FromImage(bmp);
        Init(g);
        g.Clear(Color.White);

        // 世界坐标系
        Triad(g, 210, 980, "w", 150, false);
        Txt(g, "世界坐标系", 130, 1010, fSmall);

        // 声呐机体坐标系
        float obx = 640, oby = 720;
        Triad(g, obx, oby, "b", 170, false);
        Txt(g, "声呐机体坐标系", 470, 770, fSmall);

        // 位姿变换（虚线箭头 世界系 -> 机体系）
        Arrow(g, dash, 250, 940, obx - 30, oby + 30);
        Txt(g, "位姿变换 T_i=[R_i|t_i]", 250, 850, fSmall);

        // 三维空间点 P 与观测射线（斜距 r）
        float px = 1120, py = 470;
        Node(g, px, py, 8);
        Txt(g, "空间点 P", px + 16, py - 14, fSmall);
        Arrow(g, solid, obx, oby, px, py);
        Txt(g, "斜距 r", (obx + px) / 2 + 10, (oby + py) / 2 - 44, fSmall);

        // 机体系 X_b 正方向参考线（水平前向），用于标注方位角
        Arrow(g, thin, obx, oby, obx + 300, oby);
        // 方位角 φ（X_b 正向与射线之间的弧）
        g.DrawArc(thin, obx - 70, oby - 70, 140, 140, -33, 33);
        Txt(g, "方位角 φ", obx + 140, oby - 20, fSmall);
        // 俯仰角 θ（射线偏离水平面的角，标注不可观测）
        Txt(g, "俯仰角 θ（不可观测）", obx + 250, oby - 190, fSmall);
        Arrow(g, thin, obx + 250, oby - 150, obx + 210, oby - 96);

        // 二维声呐图像平面（右侧矩形）
        float ix = 1360, iy = 250, iw = 470, ih = 560;
        g.DrawRectangle(solid, ix, iy, iw, ih);
        Txt(g, "二维声呐图像平面", ix + 90, iy - 48, fSmall);
        Txt(g, "方位向 u", ix + iw - 150, iy + 10, fSmall);
        Txt(g, "距离向 v", ix + 12, iy + ih - 38, fSmall);
        // 扇形成像区示意
        g.DrawArc(thin, ix + 50, iy + 40, 360, 680, 200, 140);
        // 投影点 与各向异性误差椭圆（对应优选①）
        float qx = ix + 250, qy = iy + 300;
        Dot(g, qx, qy, 5);
        Txt(g, "投影点 p̂", qx + 14, qy - 40, fSmall);
        g.DrawEllipse(thin, qx - 70, qy - 34, 140, 68);
        Txt(g, "σ_u", qx + 76, qy - 14, fSmall);
        Txt(g, "σ_v", qx - 26, qy - 70, fSmall);

        // 投影映射（虚线 P->p̂ + 公式）
        Arrow(g, dash, px + 12, py + 10, qx - 74, qy - 8);
        Txt(g, "投影映射  û=c_φ+f_φ·φ , v̂=c_r+f_r·r", 940, 250, fSmall);

        g.DrawString("图2  步骤S1 声学空间投影模型与坐标系关系示意图", fTitle, black,
            new RectangleF(0, H - 70, W, 50), Center());
        Save(bmp, g, path);
    }

    // ---------------- 图3 相对球坐标参数化与锚定基准帧 ----------------
    static void DrawFig3(string path)
    {
        int W = 1900, H = 1150;
        Bitmap bmp = new Bitmap(W, H);
        bmp.SetResolution(300f, 300f);
        Graphics g = Graphics.FromImage(bmp);
        Init(g);
        g.Clear(Color.White);

        // 运动轨迹（虚线弧）
        g.DrawArc(dash, 250, 200, 1400, 500, 200, 140);
        Txt(g, "声呐运动轨迹", 1500, 250, fSmall);

        // 关键帧位姿（沿轨迹）；第一个为锚定基准帧（加粗）
        float[] fx = { 360, 760, 1150, 1520 };
        float[] fy = { 360, 300, 300, 360 };
        string[] fn = { "锚定基准帧 T_b", "关键帧 T_i", "关键帧 T_k", "关键帧 T_l" };
        for (int i = 0; i < 4; i++)
        {
            Triad(g, fx[i], fy[i], "", 70, i == 0);
            Txt(g, fn[i], fx[i] - 40, fy[i] - 130, fSmall);
        }

        // 三维地标 X_j，多帧观测射线交会
        float lx = 950, ly = 820;
        Node(g, lx, ly, 9);
        Txt(g, "三维地标 X_j", lx + 16, ly + 8, fSmall);
        float[] wsw = { 3.4f, 2.2f, 1.2f, 2.0f };   // 线宽示意置信度权重
        for (int i = 0; i < 4; i++)
        {
            Pen p = new Pen(Color.Black, wsw[i]);
            g.DrawLine(p, fx[i], fy[i] + 10, lx, ly);
            p.Dispose();
        }
        Txt(g, "观测射线（线宽表示置信度权重 w_ij）", lx + 130, ly - 70, fSmall);

        // 锚定帧的相对球坐标标注（置于左侧，避免与射线交叉）
        Txt(g, "相对球坐标 [θ_j, φ_j, r_j]，初始 θ_j=0", 250, 560, fSmall);

        // 仰角弧 + 候选俯仰角搜索（对应优选③），置于右下独立区域
        float cxo = 1430, cyo = 780;
        g.DrawArc(dash, cxo - 150, cyo - 150, 300, 300, -60, 120);
        for (int k = 0; k < 5; k++)
        {
            double ang = (-60 + k * 30) * Math.PI / 180.0;
            float ex = (float)(cxo + 150 * Math.Cos(ang));
            float ey = (float)(cyo + 150 * Math.Sin(ang));
            if (k == 2) Dot(g, ex, ey, 6); else Node(g, ex, ey, 4);
        }
        Txt(g, "仰角弧上候选 θ 搜索，", cxo - 130, cyo + 172, fSmall);
        Txt(g, "取重投影一致最优 θ_j^0", cxo - 130, cyo + 208, fSmall);

        g.DrawString("图3  步骤S2 相对球坐标参数化与锚定基准帧示意图", fTitle, black,
            new RectangleF(0, H - 70, W, 50), Center());
        Save(bmp, g, path);
    }

    // ---------------- 图5 精度对比柱状图（黑白剖面线） ----------------
    static void DrawFig5(string path)
    {
        int W = 1500, H = 1100;
        Bitmap bmp = new Bitmap(W, H);
        bmp.SetResolution(300f, 300f);
        Graphics g = Graphics.FromImage(bmp);
        Init(g);
        g.Clear(Color.White);

        float left = 260, right = 1380, top = 120, bottom = 820;
        float ymax = 6f;

        // 坐标轴
        g.DrawLine(solid, left, top, left, bottom);
        g.DrawLine(solid, left, bottom, right, bottom);

        // y 轴刻度与网格
        for (int t = 0; t <= 6; t++)
        {
            float yy = bottom - (bottom - top) * t / 6f;
            g.DrawLine(thin, left - 10, yy, left, yy);
            g.DrawString(t.ToString(), fSmall, black, left - 46, yy - 14);
            if (t > 0) g.DrawLine(new Pen(Color.FromArgb(150, 150, 150), 1f) { DashStyle = DashStyle.Dot }, left, yy, right, yy);
        }

        // 纵轴标题（旋转）
        g.TranslateTransform(70, (top + bottom) / 2);
        g.RotateTransform(-90);
        g.DrawString("重投影均方根误差 / 像素", fBox, black, 0, 0, Center());
        g.ResetTransform();

        // 三个柱
        string[] names = { "传统增量式SfM\n+硬剔除BA", "无视场约束\n常规联合优化", "本发明方法" };
        float[] vals = { 5.307f, 2.6f, 1.016f };
        HatchStyle[] hs = { HatchStyle.ForwardDiagonal, HatchStyle.Cross, HatchStyle.Percent50 };
        float bw = 190;
        float slot = (right - left) / 3f;
        for (int i = 0; i < 3; i++)
        {
            float cx = left + slot * (i + 0.5f);
            float bx = cx - bw / 2;
            float bh = (bottom - top) * (vals[i] / ymax);
            float by = bottom - bh;
            Brush hb = new HatchBrush(hs[i], Color.Black, Color.White);
            g.FillRectangle(hb, bx, by, bw, bh);
            g.DrawRectangle(solid, bx, by, bw, bh);
            hb.Dispose();
            // 数值标注
            g.DrawString(vals[i].ToString("0.000"), fBox, black,
                new RectangleF(bx - 20, by - 40, bw + 40, 32), Center());
            // 方法名（x 轴下方）
            g.DrawString(names[i], fSmall, black,
                new RectangleF(cx - slot / 2, bottom + 12, slot, 90), Center());
        }

        g.DrawString("图5  不同方法的重投影精度对比", fTitle, black,
            new RectangleF(0, H - 70, W, 50), Center());

        Save(bmp, g, path);
    }

    static void Save(Bitmap bmp, Graphics g, string path)
    {
        bmp.Save(path, ImageFormat.Png);
        g.Dispose(); bmp.Dispose();
        Console.WriteLine("saved: " + path);
    }

    static void Main()
    {
        string dir = AppDomain.CurrentDomain.BaseDirectory;
        DrawFig1(Path.Combine(dir, "图1_整体流程图_黑白.png"));
        DrawFig2(Path.Combine(dir, "图2_声学投影模型_黑白.png"));
        DrawFig3(Path.Combine(dir, "图3_相对球坐标_黑白.png"));
        DrawFig4(Path.Combine(dir, "图4_S3联合优化流程图_黑白.png"));
        DrawFig5(Path.Combine(dir, "图5_精度对比_黑白.png"));
    }
}
