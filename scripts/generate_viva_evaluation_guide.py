import sys
import os
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
            self.draw_page_decorations(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(36, letter[1] - 25, "DeepFake Detection Platform — Project Evaluation & Viva Master Guide")
            self.drawRightString(letter[0] - 36, letter[1] - 25, "Student Presentation & Defense")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(36, letter[1] - 28, letter[0] - 36, letter[1] - 28)
            
        # Footer
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 36, 20, page_str)
        self.drawString(36, 20, "Academic Project Evaluation • Final Defense Reference Document")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(36, 30, letter[0] - 36, 30)
        self.restoreState()

def build_pdf(filename="DeepFake_Project_Evaluation_Viva_Guide.pdf"):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    c_primary = colors.HexColor("#0F172A")    # Deep Slate
    c_accent = colors.HexColor("#2563EB")     # Royal Blue
    c_success = colors.HexColor("#059669")    # Emerald Green
    c_danger = colors.HexColor("#DC2626")     # Crimson
    c_purple = colors.HexColor("#7C3AED")     # Violet
    c_muted = colors.HexColor("#475569")      # Slate Gray
    c_box_bg = colors.HexColor("#F8FAFC")
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
        spaceAfter=6
    )

    meta_style = ParagraphStyle(
        "MetaText",
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=c_muted,
        spaceAfter=8
    )

    part_header_style = ParagraphStyle(
        "PartHeader",
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        textColor=c_primary,
        spaceBefore=12,
        spaceAfter=5,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        "H2",
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=13,
        textColor=c_accent,
        spaceBefore=7,
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
        leading=11.5,
        textColor=colors.HexColor("#1E293B"),
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=2
    )

    speech_style = ParagraphStyle(
        "Speech",
        fontName="Helvetica-Oblique",
        fontSize=8.5,
        leading=12.5,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=4
    )

    q_style = ParagraphStyle(
        "Question",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11.5,
        textColor=c_purple,
        spaceBefore=5,
        spaceAfter=2,
        keepWithNext=True
    )

    ans_style = ParagraphStyle(
        "Answer",
        fontName="Helvetica",
        fontSize=8,
        leading=11.5,
        textColor=colors.HexColor("#1E293B"),
        spaceAfter=5
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
    story.append(Paragraph("Final Project Evaluation, Teacher Presentation Script & Viva Defense Master Guide", subtitle_style))
    story.append(Paragraph("Target Audience: Evaluator / Professor / Mam • Defense Track: AI & Cyber-Security • Author: Abhinav Kumar", meta_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=c_accent, spaceAfter=8))

    # =========================================================================
    # PART 1: The Spoken Script
    # =========================================================================
    story.append(Paragraph("PART 1: Spoken Presentation Script (How to Explain to Your Mam)", part_header_style))
    story.append(Paragraph(
        "Use this structured speech when explaining the project to your teacher or evaluator. It is divided into 4 natural stages:",
        body_style
    ))

    speech_boxes = [
        [
            Paragraph("<b>Stage 1: The Introduction & Problem Statement (30 seconds)</b><br/>"
                      "<i>\"Good morning/afternoon, Mam. Today, I am presenting our project: a DeepFake Video Detection and Cryptographic Attestation Platform. "
                      "With the rapid advancement of generative AI tools like FaceSwap, DeepFaceLab, and lip-sync models like Wav2Lip, manipulated videos are becoming "
                      "indistinguishable to the human eye. This poses severe threats to digital security, misinformation, and identity fraud. "
                      "Most existing solutions rely on single-frame image classifiers that easily fail when videos are compressed or recorded on webcams. "
                      "Our project solves this with a two-pillar approach: first, a <b>Triple-Domain Neural Network Ensemble</b> (Spatial, Spectral, and Temporal), "
                      "and second, a <b>Cryptographic Provenance Engine</b> based on C2PA standards that signs verified media with tamper-proof digital certificates.\"</i>", speech_style)
        ],
        [
            Paragraph("<b>Stage 2: How Our System Detects Fake Videos (1 minute)</b><br/>"
                      "<i>\"Mam, when a video is uploaded, our system does not just look at a single frame. It analyzes the video across three distinct visual dimensions:<br/>"
                      "1. <b>Spatial Domain (Model 1 - EfficientNet-B4)</b>: It extracts face crops and inspects pixel-level blending boundaries, warping artifacts, and synthetic facial smoothing.<br/>"
                      "2. <b>Frequency Domain (Model 2 - FrequencyCNN)</b>: It applies a 2D Discrete Cosine Transform to inspect frequency spectra. Generative AI decoders introduce periodic upsampling artifacts in the high-frequency spectrum that are invisible to humans but obvious mathematically.<br/>"
                      "3. <b>Temporal Domain (Model 3 - Temporal BiGRU)</b>: It evaluates the video across time, analyzing eye-blinking rates, micro-expressions, and frame-to-frame motion flow to detect unnatural facial jitter or lip desynchronization.<br/>"
                      "These three models are then combined through a <b>Calibrated Multi-Modal Fusion Engine</b> to output a final fake probability score.\"</i>", speech_style)
        ],
        [
            Paragraph("<b>Stage 3: The Live Demonstration Walkthrough (1 minute)</b><br/>"
                      "<i>\"Now, let me demonstrate the live platform running on our local server:<br/>"
                      "• Here is our React dashboard running on port 5173 connected to our FastAPI backend on port 8000.<br/>"
                      "• When I upload a real webcam or phone camera video, our system detects the face using centroid tracking with a tight 5% margin, passes it to the ensemble, "
                      "and outputs <b>NO_MANIPULATION_DETECTED</b> with an authentic score around 14%.<br/>"
                      "• When I upload an AI-generated deepfake (like our Face-Swap benchmark), the spatial and temporal models immediately detect the manipulation, "
                      "flagging it as <b>LIKELY_MANIPULATED</b> with over 92% confidence.<br/>"
                      "• If an irrelevant video without human faces is uploaded (such as a cooking pan), our policy engine safely marks it as <b>INCONCLUSIVE: NO_FACE_DETECTED</b>.<br/>"
                      "• Finally, for every analyzed video, our system generates an <b>Ed25519-signed digital certificate</b> with an RFC 3161 timestamp and Merkle Tree inclusion proof, proving the authenticity cryptographically.\"</i>", speech_style)
        ],
        [
            Paragraph("<b>Stage 4: Summary & Key Achievements (30 seconds)</b><br/>"
                      "<i>\"To summarize, Mam, we have retrained all three models on our GPU using over 21,500 face images and 280 video sequences from FaceForensics++ and Celeb-DF. "
                      "We passed all 80 automated unit and integration tests, solved real-world webcam false alarms, and built a complete end-to-end production pipeline. Thank you, Mam, and I am ready for any questions.\"</i>", speech_style)
        ],
    ]
    t_speech = Table(speech_boxes, colWidths=[7.4*inch])
    t_speech.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), c_box_bg),
        ("BOX", (0,0), (-1,-1), 1.0, c_accent),
        ("INNERGRID", (0,0), (-1,-1), 0.5, c_border),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
    ]))
    story.append(t_speech)
    story.append(Spacer(1, 6))

    # =========================================================================
    # PART 2: How It Distinguishes Real vs Fake
    # =========================================================================
    story.append(Paragraph("PART 2: How the Project Distinguishes Real vs Fake Videos", part_header_style))
    story.append(Paragraph(
        "When your teacher asks: <i>\"How does your model actually tell if a video is fake or real? What features is it looking at?\"</i>, "
        "explain using these three complementary visual domains:",
        body_style
    ))

    domains_table = [
        [Paragraph("<b>Domain & Model</b>", th_style), Paragraph("<b>How It Distinguishes Real vs Fake</b>", th_style), Paragraph("<b>Mathematical / Technical Mechanism</b>", th_style)],
        [
            Paragraph("<b>1. Spatial Domain</b><br/>EfficientNet-B4<br/>(Weights: 70.9 MB)", td_style),
            Paragraph("• <b>Real Videos</b>: Natural skin pores, fine wrinkles, seamless color transitions between face and neck, uniform eye pupil reflections.<br/>"
                      "• <b>Fake Videos</b>: Edge boundary blending seams where the swapped face meets original skin, abnormal warping around mouth/jawline, unnatural smoothing where facial details are blurred by generator decoders.", td_style),
            Paragraph("Passes 380×380 face crops through EfficientNet-B4 backbone. Global average pooling produces a 1792-dim feature embedding. Fine-tuned classification head detects high-contrast boundary gradients and generative artifact masks.", td_style)
        ],
        [
            Paragraph("<b>2. Frequency Domain</b><br/>FrequencyCNN (DCT)<br/>(Weights: 6.3 MB)", td_style),
            Paragraph("• <b>Real Videos</b>: Smooth, continuous energy decay in frequency space consistent with natural optical camera sensors (following natural 1/f power law).<br/>"
                      "• <b>Fake Videos</b>: Generative models (GANs, Diffusion) utilize transposed convolutions (upsampling) to generate faces, which leave periodic checkerboard artifacts and anomalous high-frequency spectral peaks invisible to the naked eye.", td_style),
            Paragraph("Applies a 2D Discrete Cosine Transform (DCT) layer with 8×8 kernels. A 5-layer CNN extracts spectral energy signatures, identifying anomalous high-frequency spikes and missing frequency bands.", td_style)
        ],
        [
            Paragraph("<b>3. Temporal Domain</b><br/>TemporalBiGRU<br/>(Weights: 2.4 MB)", td_style),
            Paragraph("• <b>Real Videos</b>: Coherent, continuous physiological motion: smooth eye blinks (lasting 100-400ms), natural jaw motion during phoneme pronunciation, consistent lighting across frames.<br/>"
                      "• <b>Fake Videos</b>: Frame-to-frame flickering, sudden micro-jitter in facial boundaries, unnatural blinking frequencies, and lip-sync desynchronization between speech and mouth geometry.", td_style),
            Paragraph("Input feature sequence normalized with LayerNorm. A Bidirectional GRU (128 hidden) with Temporal Self-Attention analyzes inter-frame continuity over sequences up to 300 frames. Detects abrupt transitions and velocity spikes.", td_style)
        ],
    ]
    t_domains = Table(domains_table, colWidths=[1.5*inch, 3.2*inch, 2.7*inch])
    t_domains.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#E2E8F0")),
        ("GRID", (0,0), (-1,-1), 0.5, c_border),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
    ]))
    story.append(t_domains)
    story.append(Spacer(1, 6))

    # =========================================================================
    # PART 3: Data Engineering & Dataset Details
    # =========================================================================
    story.append(Paragraph("PART 3: Data Engineering, Sources & Preprocessing", part_header_style))
    story.append(Paragraph(
        "When your teacher asks: <i>\"Where did you get your dataset? How much data did you use? How did you process video frames?\"</i>, "
        "provide these exact figures and engineering details:",
        body_style
    ))

    data_summary = [
        [Paragraph("<b>Dataset Attribute</b>", th_style), Paragraph("<b>Detailed Specification & Numbers</b>", th_style)],
        [Paragraph("<b>Benchmark Data Sources</b>", td_style), Paragraph("1. <b>FaceForensics++ (FF++)</b>: Industry gold-standard containing 1,000 original videos manipulated by 4 state-of-the-art algorithms: DeepFakes, Face2Face, FaceSwap, and NeuralTextures.<br/>"
                                                                       "2. <b>Celeb-DF (v2)</b>: 5,639 high-quality deepfake celebrity videos with minimal artifacts for high-difficulty testing.<br/>"
                                                                       "3. <b>Deepfake Detection Challenge (DFDC)</b>: Diverse multi-ethnic dataset collected under varied lighting, angles, and camera compressions.<br/>"
                                                                       "4. <b>In-the-Wild Real Videos</b>: Authentic smartphone recordings, laptop webcams, and YouTube broadcasts to benchmark real-world sensor profiles.", td_style)],
        [Paragraph("<b>Total Dataset Scale</b>", td_style), Paragraph("• <b>Face Frames</b>: Over <b>21,500+ extracted face images</b> across real and fake categories.<br/>"
                                                                     "• <b>Video Sequences</b>: <b>280+ complete video sequences</b> curated for temporal sequence modeling.<br/>"
                                                                     "• <b>Training / Val Split</b>: <b>885 real video folders</b> and <b>630 fake video folders</b> in training, balanced across demographics.", td_style)],
        [Paragraph("<b>Video Data Preprocessing Pipeline</b>", td_style), Paragraph("1. <b>Candidate Sampling</b>: Video demuxed via OpenCV; candidate frames uniformly sampled across video duration (up to 20 key analysis frames).<br/>"
                                                                                   "2. <b>Face Detection (Haar alt2)</b>: Gentle AdaBoost tree cascade locks onto facial coordinates (<code>minSize=45×45</code>) with 0% false positives on non-face objects.<br/>"
                                                                                   "3. <b>Centroid Identity Tracking</b>: Calculates Euclidean distance between consecutive frame face centroids. In multi-person videos, it tracks <i>one consistent subject</i> rather than jumping between people.<br/>"
                                                                                   "4. <b>5% Contour Margin</b>: Crops faces with a tight 5% padding. Excludes room shadows and shirt collars that previously caused false positives on webcams.<br/>"
                                                                                   "5. <b>Anti-Aliasing Resampling</b>: Crops resized to 380×380 using <code>cv2.INTER_AREA</code>, preventing bilinear grid interpolation artifacts.", td_style)],
        [Paragraph("<b>Hardware Acceleration</b>", td_style), Paragraph("Trained and benchmarked on <b>NVIDIA GeForce RTX 3050 Laptop GPU (6GB VRAM)</b> with CUDA 12.4, PyTorch Mixed Precision (AMP / GradScaler), and cuDNN acceleration.", td_style)],
    ]
    t_data = Table(data_summary, colWidths=[1.8*inch, 5.6*inch])
    t_data.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#E2E8F0")),
        ("GRID", (0,0), (-1,-1), 0.5, c_border),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
    ]))
    story.append(t_data)
    story.append(Spacer(1, 6))

    # =========================================================================
    # PART 4: Multi-Modal Fusion & Policy Engine
    # =========================================================================
    story.append(Paragraph("PART 4: Decision Policy & Sensor Noise Calibration", part_header_style))
    story.append(Paragraph(
        "A common flaw in academic deepfake detectors is high false positives on webcam videos due to compression artifacts. "
        "Here is how our calibrated decision policy solves this:",
        body_style
    ))
    story.append(Paragraph("• <b>The Authentic Sensor Profile Rule:</b> If Spatial Score < 0.36 and Temporal Score < 0.25 (meaning facial appearance and inter-frame motion are natural), the ensemble weights Frequency Score at only 20%. This prevents cheap webcam sensor grain from falsely triggering a 'Manipulated' verdict.", bullet_style))
    story.append(Paragraph("• <b>The Temporal Anomaly Rule:</b> If Temporal Score > 0.50 (indicating face-swapping flickering or jitter), Temporal Score receives 50% weight, ensuring dynamic deepfakes are caught even if individual frames look plausible.", bullet_style))
    story.append(Paragraph("• <b>Three-Way Verdict Structure:</b><br/>"
                           "&nbsp;&nbsp;- <b>Score < 0.38</b>: <code>NO_MANIPULATION_DETECTED</code> (Clean authentic video)<br/>"
                           "&nbsp;&nbsp;- <b>Score > 0.58</b>: <code>LIKELY_MANIPULATED</code> (Deepfake detected)<br/>"
                           "&nbsp;&nbsp;- <b>0.38 to 0.58</b>: <code>INCONCLUSIVE</code> (Borderline / human review required)<br/>"
                           "&nbsp;&nbsp;- <b>No Face Detected</b>: <code>INCONCLUSIVE (NO_FACE_DETECTED)</code> (Prevents declaring cooking pans as real or fake faces).<br/>"
                           "&nbsp;&nbsp;- <b>Short Clips (< 2s) with Verified Faces</b>: Evaluated properly via spatial/frequency models rather than forced inconclusive.", bullet_style))
    story.append(Spacer(1, 6))

    # =========================================================================
    # PART 5: Cryptographic Content Attestation
    # =========================================================================
    story.append(Paragraph("PART 5: Cryptographic Authenticity & Provenance (C2PA Model)", part_header_style))
    story.append(Paragraph(
        "Explain to your teacher that our project goes beyond simple machine learning classification by implementing an enterprise authenticity pipeline:",
        body_style
    ))
    story.append(Paragraph("1. <b>Cryptographic SHA-256 Digest</b>: Computed over the raw video byte stream to guarantee exact bit-for-bit integrity.", bullet_style))
    story.append(Paragraph("2. <b>Perceptual Hashing (pHash)</b>: Array of DCT perceptual hashes computed on face crops, allowing visual identification even after social media re-encoding.", bullet_style))
    story.append(Paragraph("3. <b>Ed25519 Asymmetric Digital Signature</b>: The analysis manifest (hashes, model versions, scores, verdict) is digitally signed with an Ed25519 private key, preventing tampering.", bullet_style))
    story.append(Paragraph("4. <b>RFC 3161 Time-Stamp Authority (TSA)</b>: The signature digest is submitted to an independent TSA, embedding legally admissible proof that the analysis occurred at that exact time.", bullet_style))
    story.append(Paragraph("5. <b>Merkle Tree Inclusion Proof</b>: The manifest hash is added as a leaf in an immutable binary Merkle Tree, allowing public verification against the published Merkle Root.", bullet_style))
    story.append(Spacer(1, 6))

    # =========================================================================
    # PART 6: Top 15 Viva Questions & Answers
    # =========================================================================
    story.append(Paragraph("PART 6: Top 15 Viva / Teacher Questions & Model Answers", part_header_style))
    story.append(Paragraph(
        "Review these questions thoroughly before your evaluation. These are the exact technical questions evaluators frequently ask:",
        body_style
    ))

    qa_list = [
        ("Q1: Why did you use an ensemble of 3 models instead of just training one single large model?",
         "Single models overfit to specific artifacts. For example, a spatial CNN only checks single images and misses temporal flickering across frames; a temporal model can miss high-frequency GAN checkerboard noise; and frequency models are sensitive to webcam sensor noise. Combining Spatial (appearance), Frequency (spectral signatures), and Temporal (motion dynamics) provides complete coverage across all deepfake artifact vectors."),
        
        ("Q2: Why EfficientNet-B4? Why not ResNet-50 or VGG-16?",
         "EfficientNet-B4 uses compound scaling (balancing depth, width, and resolution) with mobile inverted bottleneck convolutions (MBConv). It achieves 82.9% ImageNet top-1 accuracy with only 19M parameters—less than half the size of ResNet-50 (25.6M) and far smaller than VGG-16 (138M)—making inference significantly faster while capturing fine facial textures at 380×380 resolution."),
         
        ("Q3: What is the purpose of the FrequencyCNN and 2D Discrete Cosine Transform (DCT)?",
         "When generative AI models (like GANs or autoencoders) generate a face, their transposed convolution and upsampling layers create subtle periodic frequency artifacts that are invisible in the RGB color space. A 2D DCT transforms spatial pixel values into frequency components, exposing unnatural high-frequency energy spikes that distinguish synthetic faces from optical lens captures."),
         
        ("Q4: Why BiGRU for the temporal model instead of an LSTM or 3D CNN (C3D)?",
         "A Bidirectional GRU (BiGRU) has 25% fewer parameters than an LSTM (combining cell and hidden states) while capturing both past and future temporal context. 3D CNNs are computationally heavy and struggle with variable-length videos. BiGRU processes pre-extracted 1792-dim spatial embeddings with LayerNorm and Attention, running in milliseconds even on CPU."),
         
        ("Q5: What datasets did you use, and how did you split them?",
         "We used FaceForensics++ (FF++), Celeb-DF v2, and DFDC, curated into over 21,500 face frames and 280+ video sequences. The video split consists of 885 real and 630 fake video sequences in train, with dedicated validation and test sets split at the video level to prevent data leakage (frames from the same video never appear in both train and test)."),
         
        ("Q6: How does your system handle multi-person videos?",
         "Previous systems suffered from identity jumping—selecting whichever face was slightly larger each frame, which confused the temporal model. Our detector implements Euclidean Centroid Tracking: it locks onto the primary face in frame 0 and tracks that specific person by minimizing center distance across subsequent frames, ensuring temporal consistency."),
         
        ("Q7: Why did you change the face crop margin from 20% to 5%?",
         "In indoor webcam videos, a 20% margin captures background room walls, clothing collars, and shadow borders. Indoor lighting shadows on a white wall mimic synthetic cut-and-paste boundaries, causing spatial models to falsely report real videos as manipulated. A 5% margin focuses strictly on the human face (forehead, eyes, nose, mouth, chin), dropping false positives to near zero."),
         
        ("Q8: Why did you use cv2.INTER_AREA instead of standard cv2.INTER_LINEAR?",
         "Standard bilinear interpolation (INTER_LINEAR) creates grid ringing and pixel aliasing when upscaling camera crops (e.g. from 220px to 380px). The spatial model misinterprets this grid ringing as GAN generative noise. Area interpolation (INTER_AREA) uses pixel area relation, providing clean, artifact-free anti-aliasing."),
         
        ("Q9: What happens if a user uploads a video without any faces (e.g., a cooking video or a car)?",
         "Our face validation pipeline checks if valid face crops represent at least 15% of sampled frames. If no face is detected, the policy engine safely outputs INCONCLUSIVE with the reason NO_FACE_DETECTED and a default 5% baseline score. It refuses to falsely label non-face objects as authentic or fake human faces."),
         
        ("Q10: What is the significance of the 3-way verdict (NO_MANIPULATION, LIKELY_MANIPULATED, INCONCLUSIVE)?",
         "In forensic and legal applications, a binary 50% threshold is dangerous because borderline predictions (e.g. 51%) carry high uncertainty. Our policy uses an upper threshold of 0.58 for manipulated, a lower threshold of 0.38 for clean real, and reserves the 0.38-0.58 zone as INCONCLUSIVE for human forensic expert review."),
         
        ("Q11: Why is cryptographic attestation needed? Isn't AI detection enough?",
         "AI detection alone only gives a score at one moment in time. Without cryptography, an attacker could tamper with the report, modify the video bytes after inspection, or claim the analysis was backdated. By signing the manifest with Ed25519, binding it to the video's SHA-256 hash, and obtaining an RFC 3161 timestamp and Merkle proof, we guarantee non-repudiation and proof of integrity."),
         
        ("Q12: What is a Perceptual Hash (pHash) and why is it used alongside SHA-256?",
         "SHA-256 is an exact byte-level hash: changing a single bit (e.g. re-encoding on WhatsApp or YouTube) completely changes the SHA-256 hash. Perceptual hashing (pHash) computes a fingerprint based on visual frequency features. If a video is compressed or transcoded, its pHash remains virtually identical, allowing cross-platform media matching."),
         
        ("Q13: What loss function and optimizer did you use during model training?",
         "We used Binary Cross-Entropy Loss (BCELoss) with AdamW optimizer (weight decay 1e-4 for spatial/frequency, 3e-3 for temporal) and Cosine Annealing Learning Rate scheduling. Training utilized PyTorch Automatic Mixed Precision (AMP) with GradScaler on our NVIDIA RTX 3050 GPU."),
         
        ("Q14: How fast is the system? What is the inference latency?",
         "On GPU, feature extraction and 3-model inference takes approximately 1.5 to 3 seconds for a 15-second video (sampling 20 representative face frames). On CPU fallback, it completes in 6 to 9 seconds. Video upload and job processing run asynchronously in background tasks, keeping the UI responsive."),
         
        ("Q15: How did you test and validate your system?",
         "We implemented an automated test suite of 80 pytest integration tests covering authentication, video validation, policy thresholds, Ed25519 signing, RFC 3161 TSA, and Merkle tree proofs. We also built a 28-point end-to-end system check script that tests the entire lifecycle with 100% pass rate."),
    ]

    for q, a in qa_list:
        story.append(Paragraph(f"<b>{q}</b>", q_style))
        story.append(Paragraph(a, ans_style))

    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1, color=c_accent, spaceAfter=6))
    story.append(Paragraph("<b>End of Evaluation & Viva Defense Guide</b> • Best of luck with your project presentation!", ParagraphStyle("EndText", fontName="Helvetica-Bold", fontSize=9, alignment=1, textColor=c_primary)))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated Evaluation & Viva Master PDF: {filename}")

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "DeepFake_Project_Evaluation_Viva_Guide.pdf"
    build_pdf(out)
