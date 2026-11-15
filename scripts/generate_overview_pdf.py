import sys
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, PageBreak, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(36, letter[1] - 25, "DeepFake Detection & Cryptographic Attestation Platform — Technical Master Specification")
            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(0.5)
            self.line(36, letter[1] - 28, letter[0] - 36, letter[1] - 28)
            
        # Footer
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 36, 20, page_str)
        self.drawString(36, 20, "CONFIDENTIAL & PROPRIETARY — SYSTEM SPECIFICATION")
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(36, 30, letter[0] - 36, 30)
        self.restoreState()

def build_pdf(filename="DeepFake_Detection_Complete_Master_Specification.pdf"):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    c_primary = colors.HexColor("#0F172A")    # Deep slate
    c_accent = colors.HexColor("#2563EB")     # Royal blue
    c_success = colors.HexColor("#059669")    # Emerald green
    c_danger = colors.HexColor("#DC2626")     # Crimson
    c_muted = colors.HexColor("#64748B")      # Muted slate
    c_bg_light = colors.HexColor("#F8FAFC")
    c_border = colors.HexColor("#CBD5E1")

    title_style = ParagraphStyle(
        "DocTitle",
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=c_primary,
        spaceAfter=3
    )

    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        textColor=c_accent,
        spaceAfter=8
    )

    meta_style = ParagraphStyle(
        "MetaText",
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=c_muted,
        spaceAfter=10
    )

    h1_style = ParagraphStyle(
        "H1",
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=c_primary,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        "H2",
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=13,
        textColor=c_accent,
        spaceBefore=6,
        spaceAfter=3,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        "Body",
        fontName="Helvetica",
        fontSize=8,
        leading=11.5,
        textColor=colors.HexColor("#1E293B"),
        spaceAfter=4
    )

    bullet_style = ParagraphStyle(
        "Bullet",
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#1E293B"),
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=2
    )

    code_style = ParagraphStyle(
        "Code",
        fontName="Courier",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=2
    )

    th_style = ParagraphStyle(
        "TH",
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#0F172A")
    )

    td_style = ParagraphStyle(
        "TD",
        fontName="Helvetica",
        fontSize=7,
        leading=9.5,
        textColor=colors.HexColor("#1E293B")
    )

    story = []

    # Title Block
    story.append(Paragraph("DeepFake Detection & Cryptographic Attestation Platform", title_style))
    story.append(Paragraph("Comprehensive Technical Master Specification, Multi-Model Architecture & Operational Guide", subtitle_style))
    story.append(Paragraph("Platform Version: 2.1.0 • Engine: PyTorch 2.4+ CUDA • Frontend: React 18 / Vite • Backend: FastAPI / SQLAlchemy • Attestation: Ed25519 + RFC 3161 TSA + Merkle Tree", meta_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=c_accent, spaceAfter=8))

    # Section 1
    story.append(Paragraph("1. Executive Summary & Core Mission", h1_style))
    story.append(Paragraph(
        "This platform is an enterprise-grade digital media forensics and authenticity verification system designed to counter "
        "hyper-realistic AI face manipulations, face swaps (DeepFaceLab, SimSwap, RoOP), audio-driven lip-sync syntheses (Wav2Lip, SadTalker), "
        "and generative facial synthesis. It solves the critical fragility of single-domain detectors by fusing a <b>triple-model neural ensemble</b> "
        "(Spatial, Spectral, and Temporal) with an end-to-end <b>C2PA-modeled cryptographic provenance engine</b>. Every verified video produces a "
        "cryptographically signed digital attestation backed by <b>Ed25519 asymmetric signatures</b>, <b>RFC 3161 trusted timestamps</b>, and a "
        "tamper-evident <b>Merkle Tree inclusion proof</b>.",
        body_style
    ))

    # Section 2
    story.append(Paragraph("2. System Architecture & Tier Breakdown", h1_style))
    arch_data = [
        [Paragraph("<b>Tier</b>", th_style), Paragraph("<b>Component & Technology</b>", th_style), Paragraph("<b>Port / Interface</b>", th_style), Paragraph("<b>Core Responsibility</b>", th_style)],
        [Paragraph("<b>Client Tier</b>", td_style), Paragraph("React 18, Vite, Tailwind CSS, Lucide Icons", td_style), Paragraph("<code>http://localhost:5173</code>", td_style), Paragraph("Drag-and-drop upload, browser SHA-256 computation, real-time job status polling, forensic metric cards, and cryptographic manifest inspector.", td_style)],
        [Paragraph("<b>API Gateway</b>", td_style), Paragraph("FastAPI, Uvicorn, Python 3.10+, Pydantic v2", td_style), Paragraph("<code>http://localhost:8000</code>", td_style), Paragraph("RESTful endpoints for JWT authentication, video validation, job dispatch, public verification, and certificate download.", td_style)],
        [Paragraph("<b>Inference Engine</b>", td_style), Paragraph("PyTorch 2.4 (CUDA RTX 3050 / CPU Fallback)", td_style), Paragraph("Internal Pipeline", td_style), Paragraph("Gentle AdaBoost face extraction, Euclidean centroid identity tracking, feature extraction, and multi-modal ensemble fusion.", td_style)],
        [Paragraph("<b>Security & TSA</b>", td_style), Paragraph("Cryptography.io, SoftHSM, Vault, FreeTSA", td_style), Paragraph("RFC 3161 / Ed25519", td_style), Paragraph("Asymmetric manifest signing, timestamp authority querying, and binary Merkle tree ledger insertion.", td_style)],
        [Paragraph("<b>Persistence</b>", td_style), Paragraph("SQLite (WAL mode) / PostgreSQL via Async SQLAlchemy", td_style), Paragraph("Local Storage / MinIO S3", td_style), Paragraph("ACID persistence for users, videos, asynchronous jobs, cryptographic attestations, audit logs, and anomaly detection events.", td_style)],
    ]
    t_arch = Table(arch_data, colWidths=[1.1*inch, 2.0*inch, 1.4*inch, 2.9*inch])
    t_arch.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#E2E8F0")),
        ("GRID", (0,0), (-1,-1), 0.5, c_border),
        ("TOPPADDING", (0,0), (-1,-1), 2.5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2.5),
    ]))
    story.append(t_arch)
    story.append(Spacer(1, 4))

    # Section 3
    story.append(Paragraph("3. The 3-Model Neural Network Ensemble", h1_style))
    story.append(Paragraph(
        "Deepfake manipulation signatures manifest differently across visual domains. The platform coordinates three complementary models:",
        body_style
    ))

    model_data = [
        [Paragraph("<b>Model Name</b>", th_style), Paragraph("<b>Neural Architecture</b>", th_style), Paragraph("<b>Input Domain</b>", th_style), Paragraph("<b>Weights & Dim</b>", th_style), Paragraph("<b>Forensic Detection Target</b>", th_style)],
        [
            Paragraph("<b>Model 1: Spatial</b>", td_style),
            Paragraph("EfficientNet-B4<br/>(Stages 6-7 fine-tuned)", td_style),
            Paragraph("380×380 RGB Face Crop", td_style),
            Paragraph("70.9 MB<br/>1792-dim vector", td_style),
            Paragraph("Pixel-level blending boundaries, warping seams, unnatural eye/teeth textures, generative skin smoothing, and GAN boundary artifacts.", td_style)
        ],
        [
            Paragraph("<b>Model 2: Frequency</b>", td_style),
            Paragraph("FrequencyCNN<br/>(5-Layer ConvNet + DCT)", td_style),
            Paragraph("2D DCT Spectral Transform", td_style),
            Paragraph("6.3 MB<br/>256-dim head", td_style),
            Paragraph("High-frequency spectral anomalies, missing high frequencies, and periodic grid artifacts introduced by transposed convolutions in generator decoders.", td_style)
        ],
        [
            Paragraph("<b>Model 3: Temporal</b>", td_style),
            Paragraph("BiGRU + Temporal Attention<br/>(with LayerNorm & Bottleneck)", td_style),
            Paragraph("Sequence of Frame Features<br/>(T ≤ 300 frames)", td_style),
            Paragraph("2.4 MB<br/>128-dim hidden", td_style),
            Paragraph("Inter-frame motion flow, micro-jitter, identity drift, unnatural eye-blinking dynamics, and lip-sync temporal discontinuities.", td_style)
        ],
    ]
    t_models = Table(model_data, colWidths=[1.1*inch, 1.8*inch, 1.4*inch, 1.1*inch, 2.0*inch])
    t_models.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#E2E8F0")),
        ("GRID", (0,0), (-1,-1), 0.5, c_border),
        ("TOPPADDING", (0,0), (-1,-1), 2.5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2.5),
    ]))
    story.append(t_models)
    story.append(Spacer(1, 4))

    # Section 4
    story.append(Paragraph("4. Face Detection, Identity Tracking & Extraction Pipeline", h1_style))
    story.append(Paragraph(
        "High-fidelity face extraction is critical. Previous iterations suffered from false alarms on background textures and multi-person videos. "
        "The current production pipeline implements three key optimizations:",
        body_style
    ))
    story.append(Paragraph("• <b>Gentle AdaBoost Tree Cascade (haarcascade_frontalface_alt2):</b> Parameterized at <code>scaleFactor=1.1, minNeighbors=4, minSize=(45, 45)</code>. Yields 0.0% false positives on non-face scenes (e.g., cooking pans, scenery, furniture) while preserving high recall on real smartphone and laptop webcams.", bullet_style))
    story.append(Paragraph("• <b>Centroid-Based Identity Tracking:</b> In videos with multiple people, rather than blindly picking the largest face each frame, the tracker calculates Euclidean distance between consecutive centroids: <code>distance = sqrt((cx_curr - cx_prev)^2 + (cy_curr - cy_prev)^2)</code>. It locks onto the primary human subject, eliminating identity-jumping and preventing artificial 100% temporal score spikes.", bullet_style))
    story.append(Paragraph("• <b>Calibrated 5% Facial Contour Margin:</b> Tightened from an excessive 20% margin down to 5% (<code>int(fw * 0.05)</code>). Encapsulates eyes, nose, mouth, cheeks, and forehead while cleanly excluding background room shadows, wall textures, and shirt collars that previously mimicked synthetic mask edges.", bullet_style))
    story.append(Paragraph("• <b>Anti-Aliasing Resampling (cv2.INTER_AREA):</b> Bilinear interpolation creates grid ringing when upscaling crops. Using area-based decimation/resampling eliminates high-frequency pixel aliasing before tensor normalization.", bullet_style))
    story.append(Spacer(1, 4))

    # Section 5
    story.append(Paragraph("5. Multi-Modal Fusion Engine & 3-Way Policy Decision", h1_style))
    story.append(Paragraph(
        "Let <i>S</i> be the Spatial Score, <i>F</i> be the Frequency Score, and <i>T</i> be the Temporal Score. Let <i>S_top</i> and <i>F_top</i> denote the worst 1/3 outlier frames. "
        "The ensemble combines these domains through a calibrated decision tree:",
        body_style
    ))
    story.append(Paragraph("1. <b>Temporal Anomaly Rule:</b> If <code>T > 0.50</code> → <code>Ensemble = 0.50*T + 0.25*S_top + 0.25*F_top</code> (catches flickering & face-swaps).", bullet_style))
    story.append(Paragraph("2. <b>Severe Spatial Rule:</b> Else if <code>S > 0.50</code> → <code>Ensemble = 0.45*S + 0.30*S_top + 0.25*F</code> (catches blatant generative artifacts).", bullet_style))
    story.append(Paragraph("3. <b>Authentic Human Footage Rule:</b> Else if <code>S < 0.36 and T < 0.25</code> → <code>Ensemble = 0.40*T + 0.40*S + 0.20*F</code>. In authentic footage with natural motion and clear features, low-light webcam sensor noise (elevated F) is downweighted, preventing false positives.", bullet_style))
    story.append(Paragraph("4. <b>Standard / Spliced Weighted Rule:</b> Blends localized top-K outliers or falls back to balanced <code>0.40*S + 0.35*T + 0.25*F</code>.", bullet_style))
    
    story.append(Spacer(1, 3))
    policy_data = [
        [Paragraph("<b>Engine Condition</b>", th_style), Paragraph("<b>Final Verdict</b>", th_style), Paragraph("<b>Inconclusive Reason</b>", th_style), Paragraph("<b>System Behavior</b>", th_style)],
        [Paragraph("<code>has_face == False</code>", td_style), Paragraph("<b>INCONCLUSIVE</b>", td_style), Paragraph("<code>NO_FACE_DETECTED</code>", td_style), Paragraph("Video has 0 human faces (cooking, scenery). Default 5.0% score returned safely.", td_style)],
        [Paragraph("<code>duration < 2.0s</code> and <code>frames < 2</code>", td_style), Paragraph("<b>INCONCLUSIVE</b>", td_style), Paragraph("<code>TOO_SHORT</code>", td_style), Paragraph("Insufficient frames to evaluate facial presence.", td_style)],
        [Paragraph("<code>duration < 2.0s</code> and <code>frames ≥ 2</code>", td_style), Paragraph("<b>Evaluated Normally</b>", td_style), Paragraph("<code>None</code>", td_style), Paragraph("Short camera clips with verified faces are evaluated fairly (not forced to Inconclusive).", td_style)],
        [Paragraph("<code>Ensemble < 0.38</code>", td_style), Paragraph("<font color='#059669'><b>NO_MANIPULATION_DETECTED</b></font>", td_style), Paragraph("<code>None</code>", td_style), Paragraph("High confidence clean real video. Attestation stamped Authentic.", td_style)],
        [Paragraph("<code>Ensemble > 0.58</code>", td_style), Paragraph("<font color='#DC2626'><b>LIKELY_MANIPULATED</b></font>", td_style), Paragraph("<code>None</code>", td_style), Paragraph("High confidence deepfake detected. Attestation stamped Manipulated.", td_style)],
        [Paragraph("<code>0.38 ≤ Ensemble ≤ 0.58</code>", td_style), Paragraph("<b>INCONCLUSIVE</b>", td_style), Paragraph("<code>None</code>", td_style), Paragraph("Gray zone / borderline confidence requiring human forensic review.", td_style)],
    ]
    t_policy = Table(policy_data, colWidths=[1.8*inch, 1.7*inch, 1.3*inch, 2.6*inch])
    t_policy.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#E2E8F0")),
        ("GRID", (0,0), (-1,-1), 0.5, c_border),
        ("TOPPADDING", (0,0), (-1,-1), 2),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2),
    ]))
    story.append(t_policy)
    story.append(Spacer(1, 4))

    # Section 6
    story.append(Paragraph("6. Cryptographic Provenance & Attestation Engine", h1_style))
    story.append(Paragraph(
        "Every completed analysis generates a tamper-proof cryptographic attestation ensuring non-repudiation and proof of integrity:",
        body_style
    ))
    story.append(Paragraph("• <b>Dual Fingerprinting:</b> Computes both cryptographic <b>SHA-256</b> over the raw video byte stream and an array of <b>Perceptual Hashes (pHash)</b> on extracted face crops to identify the video across transcoding.", bullet_style))
    story.append(Paragraph("• <b>Ed25519 Asymmetric Digital Signature:</b> A canonical JSON manifest containing the SHA-256 hash, duration, model version fingerprints, ensemble scores, and verdict is signed using Ed25519 with local keys, SoftHSM, or HashiCorp Vault.", bullet_style))
    story.append(Paragraph("• <b>RFC 3161 Trusted Time-Stamp Authority (TSA):</b> The digital signature digest is timestamped by a compliant TSA (FreeTSA / local TSA), embedding cryptographically verifiable wall-clock proof that the analysis occurred at a specific time.", bullet_style))
    story.append(Paragraph("• <b>Merkle Tree Inclusion Proof:</b> Manifest digests are hashed into an immutable binary Merkle Tree, allowing third parties holding the video to verify authenticity against the published Merkle Root.", bullet_style))
    story.append(Spacer(1, 4))

    # Section 7
    story.append(Paragraph("7. Comprehensive Benchmark Verification Matrix", h1_style))
    story.append(Paragraph(
        "Performance across key benchmark targets in development and production testing:",
        body_style
    ))

    bench_data = [
        [Paragraph("<b>Target Video Scenario</b>", th_style), Paragraph("<b>Spatial</b>", th_style), Paragraph("<b>Freq</b>", th_style), Paragraph("<b>Temp</b>", th_style), Paragraph("<b>AI Ensemble</b>", th_style), Paragraph("<b>Final Verdict & Status</b>", th_style)],
        [Paragraph("<b>Short Camera Clip</b> (0.51s, 8 face frames)", td_style), Paragraph("9.4%", td_style), Paragraph("27.3%", td_style), Paragraph("0.1%", td_style), Paragraph("<b>9.3%</b>", td_style), Paragraph("<font color='#059669'><b>NO_MANIPULATION_DETECTED</b></font>", td_style)],
        [Paragraph("<b>User Webcam Video</b> (15.8s, multi-person)", td_style), Paragraph("13.9%", td_style), Paragraph("43.2%", td_style), Paragraph("0.1%", td_style), Paragraph("<b>14.3%</b>", td_style), Paragraph("<font color='#059669'><b>NO_MANIPULATION_DETECTED</b></font>", td_style)],
        [Paragraph("<b>YouTube F1 Broadcast</b> (Fa6cdce7LYc, cuts)", td_style), Paragraph("36.2%", td_style), Paragraph("27.5%", td_style), Paragraph("0.1%", td_style), Paragraph("<b>21.4%</b>", td_style), Paragraph("<font color='#059669'><b>NO_MANIPULATION_DETECTED</b></font>", td_style)],
        [Paragraph("<b>YouTube Prabhas Interview</b> (high motion)", td_style), Paragraph("6.1%", td_style), Paragraph("55.0%", td_style), Paragraph("0.0%", td_style), Paragraph("<b>13.4%</b>", td_style), Paragraph("<font color='#059669'><b>NO_MANIPULATION_DETECTED</b></font>", td_style)],
        [Paragraph("<b>Synthetic Deepfake Benchmark</b> (sample_fake)", td_style), Paragraph("92.4%", td_style), Paragraph("39.5%", td_style), Paragraph("100.0%", td_style), Paragraph("<b>92.7%</b>", td_style), Paragraph("<font color='#DC2626'><b>LIKELY_MANIPULATED</b></font>", td_style)],
        [Paragraph("<b>Alia Bhatt Face-Swap Reel</b> (9892d5f3...)", td_style), Paragraph("78.5%", td_style), Paragraph("61.2%", td_style), Paragraph("94.3%", td_style), Paragraph("<b>79.6%</b>", td_style), Paragraph("<font color='#DC2626'><b>LIKELY_MANIPULATED</b></font>", td_style)],
        [Paragraph("<b>Maggi Cooking Video</b> (pan, stove, no face)", td_style), Paragraph("5.0%", td_style), Paragraph("5.0%", td_style), Paragraph("5.0%", td_style), Paragraph("<b>5.0%</b>", td_style), Paragraph("<b>INCONCLUSIVE (NO_FACE_DETECTED)</b>", td_style)],
    ]
    t_bench = Table(bench_data, colWidths=[2.2*inch, 0.8*inch, 0.8*inch, 0.8*inch, 1.0*inch, 1.8*inch])
    t_bench.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#E2E8F0")),
        ("GRID", (0,0), (-1,-1), 0.5, c_border),
        ("TOPPADDING", (0,0), (-1,-1), 2),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2),
    ]))
    story.append(t_bench)
    story.append(Spacer(1, 4))

    # Section 8
    story.append(Paragraph("8. Operational Specifications, Constraints & User Guide", h1_style))
    story.append(Paragraph("• <b>File Formats:</b> MP4, WebM, MOV with H.264, H.265, VP8, or VP9 video codecs. Maximum upload size: 200 MB.", bullet_style))
    story.append(Paragraph("• <b>Face Requirements:</b> Must contain at least one visible human face (frontal or slight profile, ≥ 45×45 pixels). Videos without human faces will intentionally produce <code>INCONCLUSIVE: NO_FACE_DETECTED</code>.", bullet_style))
    story.append(Paragraph("• <b>Recommended Duration:</b> 2 to 15 seconds (30 to 300 frames) is ideal for temporal eye-blinking and micro-expression dynamics. Short clips under 2 seconds with visible faces are evaluated via spatial and frequency models.", bullet_style))
    story.append(Paragraph("• <b>Lighting:</b> Normal ambient or indoor lighting. Pitch-black scenes where facial landmarks cannot be discerned will produce no face detections.", bullet_style))
    story.append(Paragraph("• <b>Test Suite Status:</b> All 80 pytest integration & cryptographic service tests pass in 3.2s (<code>pytest backend/tests/</code>). All 28 checks in <code>comprehensive_system_check.py</code> pass with 100% compliance.", bullet_style))
    story.append(Spacer(1, 4))

    # Section 9
    story.append(Paragraph("9. Git Repository & Deployment Information", h1_style))
    story.append(Paragraph(
        "• <b>GitHub Repository:</b> <code>https://github.com/SANJu043/DeepFake-detection</code> (Branch: <code>main</code>)<br/>"
        "• <b>Production Backend:</b> <code>http://localhost:8000</code> (FastAPI / Uvicorn)<br/>"
        "• <b>Production Frontend:</b> <code>http://localhost:5173</code> (React 18 / Vite)<br/>"
        "• <b>Interactive API Docs:</b> <code>http://localhost:8000/docs</code> (Swagger UI)",
        body_style
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated master PDF document: {filename}")

if __name__ == "__main__":
    out_file = sys.argv[1] if len(sys.argv) > 1 else "DeepFake_Detection_System_Complete_Overview.pdf"
    build_pdf(out_file)
