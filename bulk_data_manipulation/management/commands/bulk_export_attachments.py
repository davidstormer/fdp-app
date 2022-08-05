import csv
import os
from django.conf import settings
from django.core.files.storage import get_storage_class
from django.core.management.base import BaseCommand
from sourcing.models import Attachment
from supporting.models import AttachmentType

help_text = """Generate a report of all attachments of a given type. Includes download links to be used by a 
download utility like wget or curl. Generates a simple script that downloads all the files one-by-one using curl."""


class Command(BaseCommand):
    help = help_text

    def add_arguments(self, parser):
        parser.add_argument('output_file', type=str)
        parser.add_argument('--type', type=str, default=None, help="Attachment type. If none given, gets all.")
        parser.add_argument('--page-num', type=int, default=0, help="Skips records by a given offset, for batching.")
        parser.add_argument('--page-size', type=int, default=1000,
                            help="Max lines to return, for batching. Default: 1000.")
        parser.add_argument('--link-expiry', type=int, default=60,
                            help="Minutes before link shared access signature (SAS) tokens expire.")

    def handle(self, *args, **options):
        page_num = options['page_num']
        page_size = options['page_size']
        if options['type']:
            attachment_type = AttachmentType.objects.get(name=options['type'])
        else:
            attachment_type = None
        if attachment_type:
            records = Attachment.objects.order_by('pk') \
                          .filter(type=attachment_type)[page_num * page_size:page_num * page_size + page_size]
        else:
            records = Attachment.objects.order_by('pk') \
                          .all()[page_num * page_size:page_num * page_size + page_size]
        if records:
            with open(options['output_file'], 'w') as csv_fd:
                with open(options['output_file'] + '.download.sh', 'w') as script_fd:
                    csv_writer = csv.DictWriter(csv_fd, ['pk', 'name', 'type', 'file_path', 'file_name', 'download_link'])
                    csv_writer.writeheader()

                    for i, record in enumerate(records):
                        try:
                            attachment_type = record.type.name
                        except AttributeError:
                            attachment_type = ''
                        try:
                            download_link = get_storage_class(settings.DEFAULT_FILE_STORAGE)() \
                                .get_sas_expiring_url(record.file.name, expiry=options['link_expiry'] * 60)
                        except AttributeError as e:
                            download_link = record.file.url
                        except ValueError as e:
                            download_link = str(e)

                        row_data = {
                            'pk': record.pk,
                            'type': attachment_type,
                            'name': record.name,
                            'file_path': record.file.name,
                            'file_name': os.path.basename(record.file.name),
                            'download_link': download_link,
                        }
                        csv_writer.writerow(row_data)

                        script_command = \
                            'curl "%s" -o "files/%s-%s"\n' % \
                            (row_data['download_link'], row_data['pk'], row_data['file_name'])
                        script_fd.write(script_command)
        else:
            self.stdout.write(self.style.ERROR('No records found, quiting...'))
            exit(1)
