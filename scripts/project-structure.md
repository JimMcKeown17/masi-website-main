# Project Structure

.
├── core
│   ├── migrations
│   │   └── __init__.py
│   ├── utils
│   │   ├── __init__.py
│   │   └── helpers.py
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── context_processors.py
│   ├── models.py
│   ├── tests.py
│   └── views.py
├── dashboards
│   ├── management
│   │   ├── commands
│   │   └── __init__.py
│   ├── migrations
│   │   ├── 0001_initial.py
│   │   ├── 0002_school_type.py
│   │   ├── 0003_alter_school_type.py
│   │   └── __init__.py
│   ├── services
│   │   ├── __init__.py
│   │   ├── airtable_service.py
│   │   └── data_processing.py
│   ├── utils
│   │   ├── __init__.py
│   │   └── text_utils.py
│   ├── visualizations
│   │   ├── __init__.py
│   │   ├── charts.py
│   │   └── mentor_charts.py
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── forms.py
│   ├── models.py
│   ├── tests.py
│   ├── urls.py
│   └── views.py
├── masi_website
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── pages
│   ├── migrations
│   │   └── __init__.py
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── tests.py
│   ├── urls.py
│   └── views.py
├── static
│   ├── css
│   │   ├── main.css
│   │   └── styles.css
│   ├── data
│   │   └── schools_list_mar14.csv
│   ├── fonts
│   ├── images
│   │   ├── 2024 Grad Magazine
│   │   ├── LCs
│   │   ├── Mid-year 2024
│   │   ├── grads
│   │   ├── logos
│   │   ├── staff
│   │   ├── AR 23 Cover Page.png
│   │   ├── About_Us_Hero_Video.mp4
│   │   ├── Alungile Magwajana (1).png
│   │   ├── Children_Video_Strip.mp4
│   │   ├── Early Childhood Education.png
│   │   ├── Eastern-Cape-1.jpg
│   │   ├── Eastern-Cape-2.JPG
│   │   ├── Eastern-Cape-3.JPG
│   │   ├── Eastern-Cape-4.JPG
│   │   ├── Eastern-Cape-5.JPG
│   │   ├── Empowering Banner_raw (1).mp4
│   │   ├── Female Staff.jpg
│   │   ├── Girls Scholarship Fund banner_small_1.mp4
│   │   ├── Graph.png
│   │   ├── Guidestar Platinum Seal.png
│   │   ├── Home_Hero_Video.mp4
│   │   ├── Home_Page_Hero_Video_2.mp4
│   │   ├── Home_Page_Hero_Video_3.mp4
│   │   ├── Home_Video_Strip.mp4
│   │   ├── Jim-Ramaphosa-Village.jpg
│   │   ├── Lit Session 1.jpg
│   │   ├── Lit Session 2.jpg
│   │   ├── Lit Session 3.jpg
│   │   ├── Lit Session 4.jpg
│   │   ├── Lit Session 5.jpg
│   │   ├── Lit Session 6.jpg
│   │   ├── Map of Qaqawuli.png
│   │   ├── Masi Colour JPEG.jpg
│   │   ├── Masi Logo Colour.png
│   │   ├── MasiLogo.webp
│   │   ├── Masinyusne Logo Colour.png
│   │   ├── Mid-Year Report 2024.jpg
│   │   ├── Nikelo Simnikiwe (1).png
│   │   ├── Our Solution.png
│   │   ├── Platinum Seal.png
│   │   ├── Potential.png
│   │   ├── Report 1 Cover.png
│   │   ├── Report Cover 2.png
│   │   ├── Report Cover 3.png
│   │   ├── Report Cover 4.png
│   │   ├── Sandwater Primary - Literacy Session 2.jpg
│   │   ├── Sinethemba - ECD [06 October 2023] edited (1).jpg
│   │   ├── Staff 1.jpg
│   │   ├── Staff 3.jpg
│   │   ├── Staff 4.jpg
│   │   ├── Staff 5.jpg
│   │   ├── Staff.jpg
│   │   ├── Strip - Child.jpg
│   │   ├── Strip - Graduate.jpg
│   │   ├── Strip - Thuto.jpg
│   │   ├── Sume Video Strip.mp4
│   │   ├── The Problem.png
│   │   ├── Website Strip - Child Red.png
│   │   ├── Website Strip - Child copy red.png
│   │   ├── Website Strip - Child.jpg
│   │   ├── Website Strip - TL 2.jpg
│   │   ├── Website Strip - TL.png
│   │   ├── Website Strip - TL_edited.png
│   │   ├── Website Strip Community jobs 2 (sml).png
│   │   ├── Youth_Video_Strip.mp4
│   │   ├── ZZ Background 3.mp4
│   │   ├── Zama Zulu.png
│   │   ├── Zazi Video Strip.mp4
│   │   ├── banner.jpg
│   │   ├── black-background.jpg
│   │   ├── book.svg
│   │   ├── children-run-school.jpg
│   │   ├── dark-background.jpg
│   │   ├── graduate-chart.png
│   │   ├── pic01.jpg
│   │   ├── pic02.jpg
│   │   ├── pic03.jpg
│   │   ├── pic04.jpg
│   │   ├── pic05.jpg
│   │   ├── pic06.jpg
│   │   ├── polar_chart_transparent.png
│   │   ├── polar_chart_transparent_white_labels.png
│   │   ├── polar_chart_transparent_white_labels_with_padding.png
│   │   ├── quote - esethu.png
│   │   ├── quote-amlindile.png
│   │   ├── quote-azama.png
│   │   ├── spider-plot.png
│   │   ├── the problem 1.png
│   │   ├── the problem 2.png
│   │   ├── the problem 3.png
│   │   ├── the problem 4.png
│   │   ├── the problem 5.png
│   │   ├── the problem 6.png
│   │   ├── the-solution-model.png
│   │   ├── tl-photo-1.webp
│   │   ├── tl-photo-2.webp
│   │   ├── tl-photo-3.webp
│   │   ├── tl-photo-4.webp
│   │   ├── tl-photo-5.webp
│   │   ├── tl-strip-yellow.webp
│   │   ├── vid thumbnail.png
│   │   ├── youth-1.webp
│   │   ├── youth-2.webp
│   │   ├── youth-3.webp
│   │   ├── youth-4.webp
│   │   ├── youth-5.webp
│   │   └── youth_jobs_thumbnail.png
│   ├── js
│   │   ├── bootstrap.bundle.min.js
│   │   ├── lightbox-plus-jquery.min.js
│   │   ├── plotly-chart.js
│   │   ├── script.js
│   │   ├── script2.js
│   │   └── script3.js
│   ├── reports
│   │   ├── 2020 Masi Annual Report.pdf
│   │   ├── 2020 Masinyusane Annual Report.pdf
│   │   ├── 2021 Children's Education & Youth Jobs - Final Report.pdf
│   │   ├── 2021 Graduates Report.pdf
│   │   ├── 2021 Masi Graduates Magazine.pdf
│   │   ├── 2022 Masi Graduates Report.pdf
│   │   ├── 2022 Masinyusane Annual Report (R).pdf
│   │   ├── 2022 Q4 Childrens Report - All Donors.pdf
│   │   ├── 2023 Masi Graduates Magazine.pdf
│   │   ├── 2023 Masinyusane Annual Report (RSA).pdf
│   │   ├── 2024 Masi Graduates Magazine.pdf
│   │   ├── 2024 Q2 Community Jobs & Childrens Education Report.pdf
│   │   ├── Masi Top Learners - 2021 Final Report.pdf
│   │   ├── Masinyusane Audited Financial Statements 2020.pdf
│   │   ├── Masinyusane Audited Financial Statements 2021.pdf
│   │   ├── Masinyusane Audited Financial Statements 2022.pdf
│   │   └── Masinyusane Audited Financial Statements 2023.pdf
│   ├── scss
│   │   ├── abstracts
│   │   ├── components
│   │   ├── layouts
│   │   ├── pages
│   │   └── main.scss
│   └── webfonts
│       ├── fa-brands-400.ttf
│       ├── fa-brands-400.woff2
│       ├── fa-regular-400.ttf
│       ├── fa-regular-400.woff2
│       ├── fa-solid-900.ttf
│       ├── fa-solid-900.woff2
│       ├── fa-v4compatibility.ttf
│       └── fa-v4compatibility.woff2
├── staticfiles
│   ├── admin
│   │   ├── css
│   │   ├── img
│   │   └── js
│   ├── css
│   │   ├── main.css
│   │   └── styles.css
│   ├── data
│   │   └── schools_list_mar14.csv
│   ├── images
│   │   ├── 2024 Grad Magazine
│   │   ├── LCs
│   │   ├── Mid-year 2024
│   │   ├── grads
│   │   ├── logos
│   │   ├── staff
│   │   ├── AR 23 Cover Page.png
│   │   ├── About_Us_Hero_Video.mp4
│   │   ├── Alungile Magwajana (1).png
│   │   ├── Children_Video_Strip.mp4
│   │   ├── Early Childhood Education.png
│   │   ├── Eastern-Cape-1.jpg
│   │   ├── Eastern-Cape-2.JPG
│   │   ├── Eastern-Cape-3.JPG
│   │   ├── Eastern-Cape-4.JPG
│   │   ├── Eastern-Cape-5.JPG
│   │   ├── Empowering Banner_raw (1).mp4
│   │   ├── Female Staff.jpg
│   │   ├── Girls Scholarship Fund banner_small_1.mp4
│   │   ├── Graph.png
│   │   ├── Guidestar Platinum Seal.png
│   │   ├── Home_Hero_Video.mp4
│   │   ├── Home_Page_Hero_Video_2.mp4
│   │   ├── Home_Page_Hero_Video_3.mp4
│   │   ├── Home_Video_Strip.mp4
│   │   ├── Jim-Ramaphosa-Village.jpg
│   │   ├── Lit Session 1.jpg
│   │   ├── Lit Session 2.jpg
│   │   ├── Lit Session 3.jpg
│   │   ├── Lit Session 4.jpg
│   │   ├── Lit Session 5.jpg
│   │   ├── Lit Session 6.jpg
│   │   ├── Map of Qaqawuli.png
│   │   ├── Masi Colour JPEG.jpg
│   │   ├── Masi Logo Colour.png
│   │   ├── MasiLogo.webp
│   │   ├── Masinyusne Logo Colour.png
│   │   ├── Mid-Year Report 2024.jpg
│   │   ├── Nikelo Simnikiwe (1).png
│   │   ├── Our Solution.png
│   │   ├── Platinum Seal.png
│   │   ├── Potential.png
│   │   ├── Report 1 Cover.png
│   │   ├── Report Cover 2.png
│   │   ├── Report Cover 3.png
│   │   ├── Report Cover 4.png
│   │   ├── Sandwater Primary - Literacy Session 2.jpg
│   │   ├── Sinethemba - ECD [06 October 2023] edited (1).jpg
│   │   ├── Staff 1.jpg
│   │   ├── Staff 3.jpg
│   │   ├── Staff 4.jpg
│   │   ├── Staff 5.jpg
│   │   ├── Staff.jpg
│   │   ├── Strip - Child.jpg
│   │   ├── Strip - Graduate.jpg
│   │   ├── Strip - Thuto.jpg
│   │   ├── Sume Video Strip.mp4
│   │   ├── The Problem.png
│   │   ├── Website Strip - Child Red.png
│   │   ├── Website Strip - Child copy red.png
│   │   ├── Website Strip - Child.jpg
│   │   ├── Website Strip - TL 2.jpg
│   │   ├── Website Strip - TL.png
│   │   ├── Website Strip - TL_edited.png
│   │   ├── Website Strip Community jobs 2 (sml).png
│   │   ├── Youth_Video_Strip.mp4
│   │   ├── ZZ Background 3.mp4
│   │   ├── Zama Zulu.png
│   │   ├── Zazi Video Strip.mp4
│   │   ├── banner.jpg
│   │   ├── black-background.jpg
│   │   ├── book.svg
│   │   ├── children-run-school.jpg
│   │   ├── dark-background.jpg
│   │   ├── graduate-chart.png
│   │   ├── pic01.jpg
│   │   ├── pic02.jpg
│   │   ├── pic03.jpg
│   │   ├── pic04.jpg
│   │   ├── pic05.jpg
│   │   ├── pic06.jpg
│   │   ├── polar_chart_transparent.png
│   │   ├── polar_chart_transparent_white_labels.png
│   │   ├── polar_chart_transparent_white_labels_with_padding.png
│   │   ├── quote - esethu.png
│   │   ├── quote-amlindile.png
│   │   ├── quote-azama.png
│   │   ├── spider-plot.png
│   │   ├── the problem 1.png
│   │   ├── the problem 2.png
│   │   ├── the problem 3.png
│   │   ├── the problem 4.png
│   │   ├── the problem 5.png
│   │   ├── the problem 6.png
│   │   ├── the-solution-model.png
│   │   ├── tl-photo-1.webp
│   │   ├── tl-photo-2.webp
│   │   ├── tl-photo-3.webp
│   │   ├── tl-photo-4.webp
│   │   ├── tl-photo-5.webp
│   │   ├── tl-strip-yellow.webp
│   │   ├── vid thumbnail.png
│   │   ├── youth-1.webp
│   │   ├── youth-2.webp
│   │   ├── youth-3.webp
│   │   ├── youth-4.webp
│   │   ├── youth-5.webp
│   │   └── youth_jobs_thumbnail.png
│   ├── js
│   │   ├── bootstrap.bundle.min.js
│   │   ├── lightbox-plus-jquery.min.js
│   │   ├── plotly-chart.js
│   │   ├── script.js
│   │   ├── script2.js
│   │   └── script3.js
│   ├── reports
│   │   ├── 2020 Masi Annual Report.pdf
│   │   ├── 2020 Masinyusane Annual Report.pdf
│   │   ├── 2021 Children's Education & Youth Jobs - Final Report.pdf
│   │   ├── 2021 Graduates Report.pdf
│   │   ├── 2021 Masi Graduates Magazine.pdf
│   │   ├── 2022 Masi Graduates Report.pdf
│   │   ├── 2022 Masinyusane Annual Report (R).pdf
│   │   ├── 2022 Q4 Childrens Report - All Donors.pdf
│   │   ├── 2023 Masi Graduates Magazine.pdf
│   │   ├── 2023 Masinyusane Annual Report (RSA).pdf
│   │   ├── 2024 Masi Graduates Magazine.pdf
│   │   ├── 2024 Q2 Community Jobs & Childrens Education Report.pdf
│   │   ├── Masi Top Learners - 2021 Final Report.pdf
│   │   ├── Masinyusane Audited Financial Statements 2020.pdf
│   │   ├── Masinyusane Audited Financial Statements 2021.pdf
│   │   ├── Masinyusane Audited Financial Statements 2022.pdf
│   │   └── Masinyusane Audited Financial Statements 2023.pdf
│   ├── scss
│   │   ├── abstracts
│   │   ├── components
│   │   ├── layouts
│   │   ├── pages
│   │   └── main.scss
│   └── webfonts
│       ├── fa-brands-400.ttf
│       ├── fa-brands-400.woff2
│       ├── fa-regular-400.ttf
│       ├── fa-regular-400.woff2
│       ├── fa-solid-900.ttf
│       ├── fa-solid-900.woff2
│       ├── fa-v4compatibility.ttf
│       └── fa-v4compatibility.woff2
├── templates
│   ├── account
│   │   └── login.html
│   ├── dashboards
│   │   ├── dashboard_main.html
│   │   ├── mentor_dashboard.html
│   │   └── mentor_visits.html
│   ├── pages
│   │   ├── about.html
│   │   ├── apply.html
│   │   ├── children.html
│   │   ├── data.html
│   │   ├── donate.html
│   │   ├── home.html
│   │   ├── impact.html
│   │   ├── masi_map_satellite.html
│   │   ├── top_learner.html
│   │   ├── where.html
│   │   └── youth.html
│   ├── partials
│   │   ├── footer.html
│   │   └── navbar.html
│   ├── registration
│   │   ├── login.html
│   │   ├── password_reset_done.html
│   │   └── password_reset_form.html
│   └── base.html
├── build.sh
├── db.sqlite3
├── delete-fake-data.py
├── export_code.py
├── export_code_short.py
├── generate-fake-data.py
├── llm_review.txt
├── llm_review_short.txt
├── manage.py
├── moonlit-botany-454016-b5-e20993bb54e0.json
├── my_snippets.txt
├── node-tree-formatter.js
├── package-lock.json
├── package.json
├── requirements.txt
└── tree-output.txt

61 directories, 355 files

