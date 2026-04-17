import base64
import os
import streamlit as st

from string import Formatter
from support.html_templates.html_templates import CVTemplates, CoverLetterTemplates
from typing import Optional


class CVBuilder:
    """Main CV builder class that handles template injection"""

    def __init__(self):
        self.templates = CVTemplates()

    def find_template_placeholders(self, template_string):
        """Find all placeholders in a template string"""
        formatter = Formatter()
        placeholders = [field_name for _, field_name, _, _ in formatter.parse(template_string) if field_name]
        return set(placeholders)

    def convert_date(self, element):
        """Convert date elements to formatted string"""
        date_string = ""
        start_date = element.start_date if element.start_date not in [None, "", "null"] else ""
        end_date = element.end_date if element.end_date not in [None, "", "null"] else ""

        if start_date and end_date:
            date_string = f"({start_date} - {end_date})"
        elif start_date:
            date_string = f"({start_date})"
        elif end_date:
            date_string = f"({end_date})"

        return date_string

    def format_experience(self, exp):
        """Format experience entry"""
        title = exp.title or ''
        company = f" - {exp.company}" if exp.company else ''
        return f"""
        <div class="entry">
            <strong>{title}{company}</strong> <span class="cv-date">{self.convert_date(exp)}</span>
            <p>{exp.description or ''}</p>
        </div>
        """

    def format_education(self, edu):
        """Format education entry"""
        title = edu.title or ''
        school = f", {edu.school_name}" if edu.school_name else ''
        return f"""
        <div class="entry">
            <strong>{title}{school}</strong> <span class="cv-date">{self.convert_date(edu)}</span>
            <p>{edu.description or ''}</p>
        </div>
        """

    def format_projects(self, proj):
        """Format project entry"""
        title = proj.title or ''
        company = f" - {proj.company}" if proj.company else ''
        return f"""
        <div class="entry">
            <strong>{title}{company}</strong> <span class="cv-date">{self.convert_date(proj)}</span>
            <p>{proj.description or ''}</p>
        </div>
        """

    def format_contact_info(self, cv):
        """Format contact information"""
        contact_parts = []

        if cv.personality.address:
            contact_parts.append(f'📍 {cv.personality.address}')
        if cv.personality.telephone:
            contact_parts.append(f'📞 {cv.personality.telephone}')
        if cv.personality.e_mail:
            contact_parts.append(f'✉️ {cv.personality.e_mail}')
        if cv.personality.linkedin_link:
            contact_parts.append(f'💼 {cv.personality.linkedin_link}')

        return " | ".join(contact_parts)

    def format_skills_list(self, skills):
        """Format skills list"""
        all_skills = []
        if skills:
            all_skills.extend(skills)
        return " • ".join(all_skills)

    def build_html_from_cv(self, cv, template_id="1", dest_dir="./"):
        """
        Build HTML from CV data using specified template

        Args:
            cv: CV data object
            template_id: ID of template to use ('1', '2', '3')
            dest_dir: Destination directory for output
        """

        # Get the template
        template_method = getattr(self.templates, f"template_{template_id}", None)
        if not template_method:
            raise ValueError(f"Template '{template_id}' not found. Available: modern, classic, minimalist")

        template = template_method()

        # Prepare data for injection
        template_data = {
            'name': cv.personality.name or '',
            'surname': cv.personality.surname or '',
            'job_title': cv.job_title or '',
            'experiences': ''.join(self.format_experience(exp) for exp in cv.experiences or []),
            'education': ''.join(self.format_education(edu) for edu in cv.education or []),
            'projects': ''.join(self.format_projects(proj) for proj in cv.projects or []),
            'contact_info': self.format_contact_info(cv),
            'hard_skills': self.format_skills_list(cv.hard_skills),
            'summary': cv.summary or '',
        }

        # Inject data into template
        html_content = template.format(**template_data)

        # Write to file
        output_path = f"{dest_dir}/cv.html"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return html_content

    def get_available_templates(self):
        """Get list of available template names"""
        return ['modern', 'classic', 'minimalist']


class CoverLetterBuilder:
    """Main Cover Letter builder class that handles template injection"""

    def __init__(self):
        self.templates = CoverLetterTemplates()

    def format_contact_info(self, cover_letter):
        """Format contact information"""
        contact_parts = {}

        contact_parts['email'] = f"{cover_letter.email} |" or ''
        contact_parts['phone'] = f"{cover_letter.phone} |" or ''
        contact_parts['linkedin'] = f'<a href="{cover_letter.linkedin}">{cover_letter.linkedin} |</a>' if cover_letter.linkedin else ''
        contact_parts['github'] = f'<a href="{cover_letter.github}">{cover_letter.github} |</a>' if cover_letter.github else ''

        return contact_parts

    def format_body_content(self, paragraphs):
        """Format body content paragraphs"""
        if not paragraphs:
            return ""

        formatted_paragraphs = []
        for paragraph in paragraphs:
            if paragraph.strip():
                formatted_paragraphs.append(f"<p>{paragraph.strip()}</p>")

        return "\n".join(formatted_paragraphs)

    def build_html_from_cover_letter(self, cover_letter, template_id="1", dest_dir="./"):
        """
        Build HTML from Cover Letter data using specified template

        Args:
            cover_letter: Cover Letter data object
            template_id: ID of template to use ('1', '2', '3')
            dest_dir: Destination directory for output
        """

        # Get the template
        template_method = getattr(self.templates, f"template_{template_id}", None)
        if not template_method:
            raise ValueError(f"Template '{template_id}' not found.")

        template = template_method()

        # Format contact info
        contact_info = self.format_contact_info(cover_letter)

        # Prepare data for injection
        template_data = {
            'name': cover_letter.name or '',
            'surname': cover_letter.surname or '',
            'current_position': cover_letter.current_position or '',
            'email': contact_info['email'],
            'phone': contact_info['phone'],
            'linkedin': contact_info['linkedin'],
            'github': contact_info['github'],
            'date': cover_letter.date,
            # 'company_name': cover_letter.company_name or '',
            # 'company_address': cover_letter.company_address or '',
            'position_title': cover_letter.position_title or '',
            'salutation': cover_letter.salutation or 'Dear Hiring Manager,',
            'body_content': self.format_body_content(cover_letter.body_paragraphs or []),
            'closing': cover_letter.closing or 'Thank you for considering my application. I look forward to hearing from you.',
        }

        # Inject data into template
        html_content = template.format(**template_data)

        # Write to file
        output_path = f"{dest_dir}/cover_letter.html"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return html_content

    def get_available_templates(self):
        """Get list of available template names"""
        return ['professional', 'modern', 'classic']


def create_pdf_download_link(pdf_bytes: bytes, filename: str) -> str:
    """Create a data URI for PDF download."""
    b64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
    return f'data:application/pdf;base64,{b64_pdf}'


def create_auto_download_html(href: str, filename: str) -> str:
    """Generate HTML that triggers automatic download."""
    return f"""
    <html>
    <body>
        <a id="autoDownload" href="{href}" download="{filename}"></a>
        <script>
            document.getElementById('autoDownload').click();
        </script>
    </body>
    </html>
    """


def read_pdf_file(file_path: str) -> Optional[bytes]:
    """Safely read PDF file and return bytes, or None if file doesn't exist."""
    if not os.path.exists(file_path):
        return None

    try:
        with open(file_path, "rb") as f:
            return f.read()
    except (IOError, OSError) as e:
        st.error(f"Error reading file {file_path}: {e}")
        return None


def trigger_pdf_downloads():
    """Main function to handle PDF downloads."""
    # Get file paths from session state
    cv_path = st.session_state.information_extractor.generated_pdf_path
    cover_letter_path = st.session_state.information_extractor.generated_cover_letter_pdf_path

    # Define download configurations
    downloads = [
        {"path": cv_path, "filename": "CV.pdf"},
        {"path": cover_letter_path, "filename": "Cover_Letter.pdf"}
    ]

    # Read and validate all files first
    pdf_data = []
    for config in downloads:
        pdf_bytes = read_pdf_file(config["path"])
        if pdf_bytes is None:
            st.error("❌ Failed to generate PDF.")
            return

        pdf_data.append({
            "bytes": pdf_bytes,
            "filename": config["filename"]
        })

    # All files exist, proceed with downloads
    st.success("✅ PDFs generated. Download should start automatically.")

    for data in pdf_data:
        href = create_pdf_download_link(data["bytes"], data["filename"])
        download_html = create_auto_download_html(href, data["filename"])
        st.components.v1.html(download_html, height=0)



def render_editable_cover_letter(final_cover_letter):
    """Render editable cover letter interface"""
    # Ensure session state is initialized
    if "cover_letter_paragraphs" not in st.session_state:
        st.session_state.cover_letter_paragraphs = final_cover_letter.body_paragraphs or []
    
    # Callback to add new paragraph
    def add_paragraph():
        st.session_state.cover_letter_paragraphs.append("")
    
    # Callback to delete paragraph at index
    def delete_paragraph(idx):
        st.session_state.cover_letter_paragraphs.pop(idx)
    
    # Personal Information
    with st.expander("👤 Personal Information", expanded=True):
        final_cover_letter.name = st.text_input(
            "Name", 
            value=final_cover_letter.name or "",
            key="cl_name"
        )
        final_cover_letter.surname = st.text_input(
            "Surname", 
            value=final_cover_letter.surname or "",
            key="cl_surname"
        )
        final_cover_letter.current_position = st.text_input(
            "Current Position", 
            value=final_cover_letter.current_position or "",
            key="cl_position"
        )
        final_cover_letter.email = st.text_input(
            "Email", 
            value=final_cover_letter.email or "",
            key="cl_email"
        )
        final_cover_letter.phone = st.text_input(
            "Phone", 
            value=final_cover_letter.phone or "",
            key="cl_phone"
        )
        final_cover_letter.linkedin = st.text_input(
            "LinkedIn", 
            value=final_cover_letter.linkedin or "",
            key="cl_linkedin"
        )
        final_cover_letter.github = st.text_input(
            "GitHub", 
            value=final_cover_letter.github or "",
            key="cl_github"
        )
    
    # Cover Letter Content
    with st.expander("✉️ Cover Letter Content", expanded=True):
        final_cover_letter.salutation = st.text_input(
            "Salutation", 
            value=final_cover_letter.salutation or "Dear Hiring Manager,",
            key="cl_salutation"
        )
        
        st.markdown("**Body Paragraphs:**")
        for i, paragraph in enumerate(st.session_state.cover_letter_paragraphs):
            col1, col2 = st.columns([0.9, 0.1])
            with col1:
                st.session_state.cover_letter_paragraphs[i] = st.text_area(
                    f"Paragraph {i+1}", 
                    paragraph, 
                    key=f"cl_para_{i}",
                    height=100
                )
            with col2:
                st.button("❌", key=f"cl_del_para_{i}", on_click=delete_paragraph, args=(i,))
        
        st.button("➕ Add Paragraph", on_click=add_paragraph, key="cl_add_para_btn")
        
        final_cover_letter.closing = st.text_input(
            "Closing", 
            value=final_cover_letter.closing or "Thank you for considering my application. I look forward to hearing from you.",
            key="cl_closing"
        )
    
    # Job Information
    with st.expander("💼 Job Information", expanded=True):
        final_cover_letter.position_title = st.text_input(
            "Position Title", 
            value=final_cover_letter.position_title or "",
            key="cl_job_title"
        )
        final_cover_letter.company_name = st.text_input(
            "Company Name", 
            value=final_cover_letter.company_name or "",
            key="cl_company"
        )
        final_cover_letter.recipient_name = st.text_input(
            "Recipient Name (optional)", 
            value=final_cover_letter.recipient_name or "",
            key="cl_recipient"
        )
        final_cover_letter.company_address = st.text_input(
            "Company Address (optional)", 
            value=final_cover_letter.company_address or "",
            key="cl_address"
        )
    
    # Template Selection
    with st.expander("🎨 Template Selection", expanded=True):
        template_options = {
            "Template 1": "1",
            #"Template 2": "2",
            # Add more templates as needed
        }
        selected_template_label = st.selectbox(
            "Choose a template", 
            list(template_options.keys()),
            key="cl_template_select"
        )
        st.session_state.cover_letter_template_id = template_options[selected_template_label]
    
    # Apply Changes Button
    if st.button("✅ Apply Cover Letter Changes", key="cl_apply_btn"):
        # Update body paragraphs
        final_cover_letter.body_paragraphs = st.session_state.cover_letter_paragraphs
        
        # Update job description information to match cover letter
        if "information_extractor" in st.session_state:
            # Use the new method to update job description information
            success = st.session_state.information_extractor.update_jd_from_cover_letter(final_cover_letter)
            if success:
                st.success("✅ Job description information also updated!")
            else:
                st.warning("⚠️ Job description information update failed, but cover letter changes were applied.")
        
        st.success("✅ Cover letter changes applied!")
        
        # Update session state
        if "information_extractor" in st.session_state:
            st.session_state.information_extractor.final_cover_letter = final_cover_letter
            st.session_state.generated_html_cover_letter = st.session_state.information_extractor.build_final_cover_letter(
                update_final_cover_letter=True,
                template_id=st.session_state.cover_letter_template_id
            )
            
            # Update database if submission exists
            if hasattr(st.session_state, 'current_submission_id') and st.session_state.current_submission_id:
                try:
                    from support.submission_manager import update_submission, get_all_submissions
                    # Get the latest submission to update
                    all_submissions = get_all_submissions()
                    if all_submissions:
                        latest_submission_id = all_submissions[-1][0]
                        # Update the submission with new cover letter data
                        update_submission(
                            latest_submission_id,
                            st.session_state.information_extractor.final_cv,
                            st.session_state.information_extractor.final_cover_letter,
                            st.session_state.information_extractor.jd_information
                        )
                        st.success("✅ Database updated with cover letter changes!")
                except Exception as e:
                    st.warning(f"⚠️ Database update failed: {e}")


a4_style = """
<div style="
    width: 794px;
    height: 1123px;
    margin: 10px 10px;
    box-shadow: 0 0 10px rgba(0, 0, 0, 0.2), 0 -5px 10px rgba(0, 0, 0, 0.4), 0 5px 10px rgba(0, 0, 0, 0.4);
    padding: 40px;
    background-color: white;
    overflow: hidden;
">
    {}
</div>
"""

_IFRAME_RESET_CSS = """
<style>
  html, body {
    background-color: #ffffff !important;
    color: #111827 !important;
  }
</style>
"""


def inject_iframe_reset(html: str) -> str:
    """Inject a white-background CSS reset so Streamlit's dark theme
    doesn't bleed into st.components.v1.html iframes."""
    if "</head>" in html:
        return html.replace("</head>", _IFRAME_RESET_CSS + "</head>", 1)
    return _IFRAME_RESET_CSS + html


