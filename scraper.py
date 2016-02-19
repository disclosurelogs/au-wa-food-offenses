import pdfquery
import scraperwiki
from bs4 import BeautifulSoup
import StringIO
import re

data_exists = scraperwiki.sql.select("count(*) FROM sqlite_master WHERE type='table' AND name='data';")[0]["count(*)"]> 0

base_url = "http://ww2.health.wa.gov.au"
html = scraperwiki.scrape("http://ww2.health.wa.gov.au/Articles/F_I/Food-offenders/Publication-of-names-of-offenders-list")

soup = BeautifulSoup(html, "html5lib")
missing_notices = []

pdf_size = re.compile("\(PDF.*")

for tr in soup.tbody.find_all('tr'):
    notice = {}
    notice['date_of_conviction'] = tr.find_all('td')[0].text
    notice['business_name'] = pdf_size.sub("",tr.find_all('td')[1].a.text).strip()
    notice['notice_pdf_url'] = base_url + tr.find_all('td')[1].a.get('href').replace(' ', '%20')
    notice['business_location'] = tr.find_all('td')[1].text.strip().split("\n")[1].strip()
    notice['convicted_persons'] = tr.find_all('td')[2].text.strip()
    notice['enforcement_agency'] = tr.find_all('td')[3].text.strip()
    if not data_exists:
        missing_notices.append(notice)
    else:
        existing_notice = int(scraperwiki.sql.select("count(*) from data where notice_pdf_url = ?",
                                                 [notice['notice_pdf_url']])[0]["count(*)"]) > 0
        if not existing_notice:
            missing_notices.append(notice)



page_width = 595.32
page_height = 841.92
col_1_end_x = 196
col_2_end_x = 450

for notice in missing_notices:
    if True:
        print notice["notice_pdf_url"]
        binary = StringIO.StringIO(scraperwiki.scrape(notice["notice_pdf_url"]))
        #binary = open('test.pdf')
        pdf = pdfquery.PDFQuery(binary,merge_tags=('LTChar', 'LTAnon','LTTextLineHorizontal'),
                                resort=True)#, parse_tree_cacher=FileCache("/tmp/"))
        pdf.load()
        #pdf.tree.write("test.xml", pretty_print=True, encoding="utf-8")

        if pdf.pq('LTTextBoxHorizontal:contains("Date of offence")'):
            abn_x = float(pdf.pq('LTTextBoxHorizontal:contains("Date of offence")').attr('x1'))
            abn_y = float(pdf.pq('LTTextBoxHorizontal:contains("Date of offence")').attr('y0'))
        notice['date_of_offence'] = pdf.pq(
            'LTTextBoxHorizontal:in_bbox("%s, %s, %s, %s")' % (abn_x, abn_y, page_width, abn_y + 15))\
            .text().strip()

        page_1_table_y = float(pdf.pq('LTTextBoxHorizontal:contains("egislation")').attr('y1'))
        legislation = pdf.pq(':in_bbox("%s, %s, %s, %s")' % (
            0 , 0,col_1_end_x+20, page_1_table_y-20))
        notice['legislation'] = legislation.text().strip()

        penalty = pdf.pq('LTTextBoxHorizontal:in_bbox("%s, %s, %s, %s") ' % (
            col_2_end_x , 50, page_width, page_1_table_y))
        notice['penalty'] = penalty.text().strip()

        notice['offence_details'] = ' '
        offence_details = pdf.pq('LTPage[page_index="0"] :in_bbox("%s, %s, %s, %s")' % (
            col_1_end_x, 0, col_2_end_x, page_1_table_y))
        notice['offence_details'] += offence_details.text().strip()

        offence_details2 = pdf.pq('LTPage[page_index="1"] :in_bbox("%s, %s, %s, %s")' % (
            col_1_end_x, 0, col_2_end_x, page_height))
        notice['offence_details'] += ' '+ offence_details2.text().strip()

        #if all else fails, try try again
        if notice['offence_details'].strip() == '':
            text = pdf.pq('LTTextBoxHorizontal').text().strip()
            result = re.findall("(Non-compliance.*)( 1 *?)",text)
            if result[0]:
                notice['offence_details'] = result[0][0].strip()


        scraperwiki.sql.save(unique_keys=["notice_pdf_url"], data=notice)
