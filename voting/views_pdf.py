import hashlib
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.utils import timezone
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas

from .models import Student, VoterRegistration
from .views import _active_election_or_none


class NumberedCanvas(canvas.Canvas):
	"""
	Canvas to dynamically compute and render 'Page X of Y' in a two-pass layout,
	adding a clean page rule and footer accent.
	"""
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._saved_page_states = []

	def showPage(self):
		self._saved_page_states.append(dict(self.__dict__))
		self._startPage()

	def save(self):
		num_pages = len(self._saved_page_states)
		for state in self._saved_page_states:
			self.__dict__.update(state)
			self.draw_page_number(num_pages)
			super().showPage()
		super().save()

	def draw_page_number(self, page_count):
		self.saveState()
		self.setFont("Helvetica", 8)
		self.setFillColor(colors.HexColor("#5f6f94"))

		# Footer text & page numbering
		page_text = f"Page {self._pageNumber} of {page_count}"
		self.drawRightString(612 - 36, 22, page_text)
		self.drawString(36, 22, "E-Voting System — Student Status Report (Confidential)")

		# Subtle horizontal rule above footer text
		self.setStrokeColor(colors.HexColor("#e2e8f0"))
		self.setLineWidth(0.5)
		self.line(36, 32, 612 - 36, 32)

		self.restoreState()


@login_required
def download_student_status_pdf(request):
	"""
	Generates a styled, print-ready PDF containing the lists of voted, non-voted,
	or all students matching the current school's active election.
	"""
	profile = getattr(request.user, "profile", None)
	if not (
		request.user.is_superuser
		or (
			profile
			and not profile.is_locked
			and profile.role in ("invigilator", "teacher")
		)
	):
		return HttpResponse("Access denied.", status=403)

	school_slug = request.GET.get("school_slug", "").strip() or None
	if not request.user.is_superuser and profile and profile.school_slug:
		school_slug = profile.school_slug

	election = _active_election_or_none(school_slug=school_slug)
	if not election:
		raise Http404("No active election found.")

	status = request.GET.get("status", "all").strip().lower()
	if status not in ("voted", "non-voted", "all"):
		status = "all"

	# Fetch students sorted by class, division, and name
	students = Student.objects.filter(election=election).order_by(
		"student_class", "division", "name"
	)

	# Fetch voter registrations for the election to determine voted state
	voted_hashes = set(
		VoterRegistration.objects.filter(election=election).values_list(
			"student_id_hash", flat=True
		)
	)

	voted_students = []
	non_voted_students = []
	all_students = []

	for s in students:
		val = (
			s.student_id.lower()
			if s.student_id
			else f"student_id__{s.id}"
		)
		h = hashlib.sha256(f"{election.id}:{val}".encode("utf-8")).hexdigest()
		has_voted = h in voted_hashes

		item = {
			"sno": 0,
			"name": s.name,
			"class_div": (
				f"Class {s.student_class} - {s.division}"
				if s.division
				else f"Class {s.student_class}"
			),
			"student_id": s.student_id or "-",
			"status_text": "Voted" if has_voted else "Not Voted",
		}

		all_students.append(item)
		if has_voted:
			voted_students.append(item)
		else:
			non_voted_students.append(item)

	# Choose lists based on requested report status
	if status == "voted":
		target_list = voted_students
		report_title = "Voted Students List"
		accent_color = colors.HexColor("#148449")
	elif status == "non-voted":
		target_list = non_voted_students
		report_title = "Non-Voted Students List"
		accent_color = colors.HexColor("#a56700")
	else:
		target_list = all_students
		report_title = "Voter Turnout Report (Full Roster)"
		accent_color = colors.HexColor("#0f5ad6")

	# Setup serial numbers
	for idx, item in enumerate(target_list, 1):
		item["sno"] = idx

	# Setup HTTP response
	response = HttpResponse(content_type="application/pdf")
	timestamp = timezone.now().strftime("%Y%m%d_%H%M")
	filename = f"{election.school_slug}_voters_{status}_{timestamp}.pdf"
	response["Content-Disposition"] = f'attachment; filename="{filename}"'

	# SimpleDocTemplate with 0.5-inch margins (Letter: 612 x 792pt)
	doc = SimpleDocTemplate(
		response,
		pagesize=letter,
		leftMargin=36,
		rightMargin=36,
		topMargin=36,
		bottomMargin=46,
	)

	styles = getSampleStyleSheet()

	# Custom paragraph styles matching the global theme
	school_style = ParagraphStyle(
		"SchoolTitle",
		parent=styles["Normal"],
		fontName="Helvetica-Bold",
		fontSize=18,
		leading=22,
		textColor=colors.HexColor("#12213f"),
	)
	meta_style = ParagraphStyle(
		"MetaText",
		parent=styles["Normal"],
		fontName="Helvetica",
		fontSize=9,
		leading=13,
		textColor=colors.HexColor("#5f6f94"),
	)

	story = []

	# 1. Header Information Block
	header_data = [
		[
			Paragraph(f"<b>{election.school_name}</b>", school_style),
			Paragraph(
				f"<b>Date:</b> {timezone.now().strftime('%d-%b-%Y %I:%M %p')}<br/><b>Format:</b> PDF Report",
				meta_style,
			),
		],
		[
			Paragraph(
				f"Election: <b>{election.title}</b>",
				ParagraphStyle(
					"ElectionSub",
					parent=styles["Normal"],
					fontName="Helvetica",
					fontSize=11,
					leading=15,
					textColor=colors.HexColor("#5f6f94"),
				),
			),
			Paragraph(
				f"<b>Scope:</b> {status.upper()}",
				meta_style,
			),
		],
	]
	header_table = Table(header_data, colWidths=[360, 180])
	header_table.setStyle(
		TableStyle(
			[
				("VALIGN", (0, 0), (-1, -1), "TOP"),
				("ALIGN", (1, 0), (1, -1), "RIGHT"),
				("BOTTOMPADDING", (0, 0), (-1, -1), 0),
				("TOPPADDING", (0, 0), (-1, -1), 0),
			]
		)
	)
	story.append(header_table)
	story.append(Spacer(1, 8))

	# Divider line
	divider = Table([[""]], colWidths=[540])
	divider.setStyle(
		TableStyle(
			[
				("LINEBELOW", (0, 0), (-1, -1), 1.5, colors.HexColor("#0f5ad6")),
				("BOTTOMPADDING", (0, 0), (-1, -1), 0),
				("TOPPADDING", (0, 0), (-1, -1), 0),
			]
		)
	)
	story.append(divider)
	story.append(Spacer(1, 12))

	# 2. Report Category Title
	story.append(
		Paragraph(
			f"<b>{report_title}</b>",
			ParagraphStyle(
				"CategoryTitle",
				parent=styles["Normal"],
				fontName="Helvetica-Bold",
				fontSize=14,
				leading=18,
				textColor=accent_color,
			),
		)
	)
	story.append(Spacer(1, 8))

	# 3. Summary Dashboard Cards (4-column block)
	v_count = len(voted_students)
	nv_count = len(non_voted_students)
	total_cnt = len(all_students)
	pct = (v_count / total_cnt * 100) if total_cnt > 0 else 0.0

	summary_data = [
		[
			Paragraph(
				f"<font size=8 color='#5f6f94'>TOTAL ROSTER</font><br/><font size=16 color='#12213f'><b>{total_cnt}</b></font>",
				styles["Normal"],
			),
			Paragraph(
				f"<font size=8 color='#5f6f94'>VOTED</font><br/><font size=16 color='#148449'><b>{v_count}</b></font>",
				styles["Normal"],
			),
			Paragraph(
				f"<font size=8 color='#5f6f94'>NON-VOTED</font><br/><font size=16 color='#a56700'><b>{nv_count}</b></font>",
				styles["Normal"],
			),
			Paragraph(
				f"<font size=8 color='#5f6f94'>TURNOUT RATE</font><br/><font size=16 color='#0f5ad6'><b>{pct:.1f}%</b></font>",
				styles["Normal"],
			),
		]
	]
	summary_table = Table(summary_data, colWidths=[135, 135, 135, 135])
	summary_table.setStyle(
		TableStyle(
			[
				("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
				("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
				("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
				("TOPPADDING", (0, 0), (-1, -1), 8),
				("BOTTOMPADDING", (0, 0), (-1, -1), 8),
				("LEFTPADDING", (0, 0), (-1, -1), 10),
				("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
			]
		)
	)
	story.append(summary_table)
	story.append(Spacer(1, 16))

	# 4. Roster Table
	th_style = ParagraphStyle(
		"TableHeader",
		parent=styles["Normal"],
		fontName="Helvetica-Bold",
		fontSize=9,
		textColor=colors.white,
	)
	headers = [
		Paragraph("S.No.", th_style),
		Paragraph("Student Name", th_style),
		Paragraph("Class & Division", th_style),
		Paragraph("Student ID / Admission No.", th_style),
		Paragraph("Status", th_style),
	]
	table_rows = [headers]

	td_style = ParagraphStyle(
		"TableCell",
		parent=styles["Normal"],
		fontName="Helvetica",
		fontSize=9,
		leading=13,
		textColor=colors.HexColor("#12213f"),
	)

	for item in target_list:
		status_pill_color = "#148449" if item["status_text"] == "Voted" else "#a56700"
		status_html = f"<b><font color='{status_pill_color}'>{item['status_text']}</font></b>"
		row = [
			Paragraph(str(item["sno"]), td_style),
			Paragraph(f"<b>{item['name']}</b>", td_style),
			Paragraph(item["class_div"], td_style),
			Paragraph(item["student_id"], td_style),
			Paragraph(status_html, td_style),
		]
		table_rows.append(row)

	# Handle empty lists gracefully
	if not target_list:
		empty_p = Paragraph(
			"No students found matching this status.",
			ParagraphStyle(
				"EmptyCell",
				parent=td_style,
				alignment=1,
				textColor=colors.HexColor("#5f6f94"),
			),
		)
		table_rows.append([empty_p, "", "", "", ""])

	# Column widths sum to 540pt (612pt - 72pt total horizontal margins)
	col_widths = [35, 205, 110, 110, 80]
	student_table = Table(table_rows, colWidths=col_widths, repeatRows=1)

	# Roster Table Styles
	t_styles = [
		("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#12213f")),
		("ALIGN", (0, 0), (-1, -1), "LEFT"),
		("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
		("TOPPADDING", (0, 0), (-1, -1), 6),
		("BOTTOMPADDING", (0, 0), (-1, -1), 6),
		("LEFTPADDING", (0, 0), (-1, -1), 8),
		("RIGHTPADDING", (0, 0), (-1, -1), 8),
		("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
		("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
	]

	# Apply alternating background shading to rows
	for i in range(1, len(table_rows)):
		bg = colors.HexColor("#ffffff") if i % 2 != 0 else colors.HexColor("#f8fafc")
		t_styles.append(("BACKGROUND", (0, i), (-1, i), bg))

	if not target_list:
		t_styles.append(("SPAN", (0, 1), (-1, 1)))

	student_table.setStyle(TableStyle(t_styles))
	story.append(student_table)

	# Build doc using NumberedCanvas
	doc.build(story, canvasmaker=NumberedCanvas)
	return response
