using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.IO;

class DrawRoute
{
    static Graphics g;
    static Font fTitle, fBox, fLabel, fSmall;

    static void Box(float x, float y, float w, float h, string text, Color fill, Font f)
    {
        using (Brush b = new SolidBrush(fill))
            g.FillRectangle(b, x, y, w, h);
        using (Pen p = new Pen(Color.FromArgb(80, 80, 80), 1.5f))
            g.DrawRectangle(p, x, y, w, h);
        StringFormat sf = new StringFormat();
        sf.Alignment = StringAlignment.Center;
        sf.LineAlignment = StringAlignment.Center;
        g.DrawString(text, f, Brushes.Black, new RectangleF(x, y, w, h), sf);
    }

    static void Arrow(float x1, float y1, float x2, float y2, string label, bool dashed)
    {
        using (Pen p = new Pen(dashed ? Color.FromArgb(120, 120, 120) : Color.Black, 2f))
        {
            if (dashed) p.DashStyle = DashStyle.Dash;
            p.CustomEndCap = new AdjustableArrowCap(5, 5);
            g.DrawLine(p, x1, y1, x2, y2);
        }
        if (!string.IsNullOrEmpty(label))
        {
            float mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
            g.DrawString(label, fSmall, Brushes.DarkBlue, mx + 4, my - 8);
        }
    }

    static void Main()
    {
        int W = 1260, H = 860;
        Bitmap bmp = new Bitmap(W, H);
        g = Graphics.FromImage(bmp);
        g.SmoothingMode = SmoothingMode.AntiAlias;
        g.TextRenderingHint = System.Drawing.Text.TextRenderingHint.ClearTypeGridFit;
        g.Clear(Color.White);

        fTitle = new Font("Microsoft YaHei", 17, FontStyle.Bold);
        fBox = new Font("Microsoft YaHei", 11, FontStyle.Regular);
        fLabel = new Font("Microsoft YaHei", 11, FontStyle.Bold);
        fSmall = new Font("Microsoft YaHei", 9, FontStyle.Regular);

        Color cInput = Color.FromArgb(230, 236, 245);
        Color cLayer2 = Color.FromArgb(226, 242, 232);
        Color cLayer1 = Color.FromArgb(235, 232, 245);
        Color cCore = Color.FromArgb(250, 226, 210);
        Color cMod = Color.FromArgb(240, 248, 240);
        Color cMod1 = Color.FromArgb(240, 238, 250);
        Color cOut = Color.FromArgb(232, 240, 250);
        Color cFinal = Color.FromArgb(252, 236, 200);

        StringFormat sfL = new StringFormat();
        sfL.Alignment = StringAlignment.Near; sfL.LineAlignment = StringAlignment.Near;

        // Title
        g.DrawString("水下声呐三维重建 —— 两创新点耦合总体技术路线", fTitle, Brushes.Black, 250, 16);

        // Input
        Box(370, 62, 520, 46, "水下声呐图像序列 + 平台里程计", cInput, fBox);

        // Layer 2 container (创新点二)
        Box(90, 150, 1080, 190, "", cLayer2, fBox);
        g.DrawString("创新点二：ViT+LoRA 语义-结构引导（图像理解层）", fLabel, Brushes.DarkGreen,
            new RectangleF(104, 158, 1000, 24), sfL);
        Box(120, 200, 320, 120, "模块一\n目标-背景分割\n→ 目标掩码", cMod, fBox);
        Box(470, 200, 320, 120, "模块二（核心）\n声学阴影分割 + 高度反演\n→ 高度/仰角先验", cCore, fBox);
        Box(820, 200, 320, 120, "模块三\n语义一致性关联\n→ 语义关联约束", cMod, fBox);

        // arrows from layer2 to layer1
        Arrow(280, 340, 280, 408, "去杂波", false);
        Arrow(630, 340, 630, 408, "补仰角/高度", false);
        Arrow(980, 340, 980, 408, "提关联", false);

        // Layer 1 container (创新点一)
        Box(90, 410, 1080, 150, "", cLayer1, fBox);
        g.DrawString("创新点一：数据关联与位姿联合优化鲁棒 BA（几何优化层）", fLabel, Brushes.Indigo,
            new RectangleF(104, 418, 1000, 24), sfL);
        Box(120, 456, 1020, 86,
            "软数据关联置信度   ·   相对球坐标 + 视场硬约束   ·   位姿-地标联合优化   ·   置信度引导加权曲面重建",
            cMod1, fBox);

        // arrow to output
        Arrow(630, 560, 630, 606, "", false);
        Box(370, 606, 520, 46, "高精度位姿 + 高保真三维点云/网格", cOut, fBox);

        // arrow to final
        Arrow(630, 652, 630, 700, "", false);
        Box(350, 700, 560, 52, "最终目标：高质量水下声呐三维重建", cFinal, fLabel);

        // feedback dashed arrow (output -> layer2 right side)
        using (Pen p = new Pen(Color.FromArgb(120, 120, 120), 2f))
        {
            p.DashStyle = DashStyle.Dash;
            p.CustomEndCap = new AdjustableArrowCap(5, 5);
            PointF[] pts = new PointF[] {
                new PointF(890, 629), new PointF(1210, 629),
                new PointF(1210, 260), new PointF(1170, 260)
            };
            g.DrawLines(p, pts);
        }
        g.DrawString("可选反哺：投影一致性校验 → 改进分割", fSmall, Brushes.DimGray, 1000, 632);

        string outPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "总体技术路线图.png");
        bmp.Save(outPath, ImageFormat.Png);
        g.Dispose(); bmp.Dispose();
        Console.WriteLine("saved: " + outPath);
    }
}
