# Generated by Django 3.1.3 on 2021-02-11 08:25

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('fdpuser', '0001_initial'),
        ('supporting', '0001_initial'),
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='person',
            name='fdp_organizations',
            field=models.ManyToManyField(blank=True, db_table='fdp_person_fdp_organization', help_text='FDP organizations, which have exclusive access to person. Leave blank if all registered users can access.', related_name='persons', related_query_name='person', to='fdpuser.FdpOrganization', verbose_name='organization access'),
        ),
        migrations.AddField(
            model_name='person',
            name='traits',
            field=models.ManyToManyField(blank=True, db_table='fdp_person_trait', help_text='Traits used to describe the person', related_name='persons', related_query_name='person', to='supporting.Trait', verbose_name='traits'),
        ),
        migrations.AddField(
            model_name='incident',
            name='encounter_reason',
            field=models.ForeignKey(blank=True, help_text='Reason for encounter during incident', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='incidents', related_query_name='incident', to='supporting.encounterreason', verbose_name='encounter reason'),
        ),
        migrations.AddField(
            model_name='incident',
            name='fdp_organizations',
            field=models.ManyToManyField(blank=True, db_table='fdp_incident_fdp_organization', help_text='FDP organizations, which have exclusive access to incident. Leave blank if all registered users can access.', related_name='incidents', related_query_name='incident', to='fdpuser.FdpOrganization', verbose_name='organization access'),
        ),
        migrations.AddField(
            model_name='incident',
            name='location',
            field=models.ForeignKey(blank=True, help_text='Location where incident occurred', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='incidents', related_query_name='incident', to='supporting.location', verbose_name='location'),
        ),
        migrations.AddField(
            model_name='incident',
            name='location_type',
            field=models.ForeignKey(blank=True, help_text='Type of location where incident occurred', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='incidents', related_query_name='incident', to='supporting.incidentlocationtype', verbose_name='location type'),
        ),
        migrations.AddField(
            model_name='incident',
            name='tags',
            field=models.ManyToManyField(blank=True, db_table='fdp_incident_incident_tag', help_text='Tags describing incident', related_name='incidents', related_query_name='incident', to='supporting.IncidentTag', verbose_name='tags'),
        ),
        migrations.AddField(
            model_name='groupingrelationship',
            name='object_grouping',
            field=models.ForeignKey(help_text='Object grouping in the relationship defined by subject verb object', on_delete=django.db.models.deletion.CASCADE, related_name='object_grouping_relationships', related_query_name='object_grouping_relationship', to='core.grouping', verbose_name='object grouping'),
        ),
        migrations.AddField(
            model_name='groupingrelationship',
            name='subject_grouping',
            field=models.ForeignKey(help_text='Subject grouping in the relationship defined by "subject verb object"', on_delete=django.db.models.deletion.CASCADE, related_name='subject_grouping_relationships', related_query_name='subject_grouping_relationship', to='core.grouping', verbose_name='subject grouping'),
        ),
        migrations.AddField(
            model_name='groupingrelationship',
            name='type',
            field=models.ForeignKey(help_text='Defines the relationship, i.e. the verb portion of "subject verb object"', on_delete=django.db.models.deletion.CASCADE, related_name='grouping_relationships', related_query_name='grouping_relationship', to='supporting.groupingrelationshiptype', verbose_name='relationship'),
        ),
        migrations.AddField(
            model_name='groupingincident',
            name='grouping',
            field=models.ForeignKey(help_text='Grouping which is linked to the incident', on_delete=django.db.models.deletion.CASCADE, related_name='grouping_incidents', related_query_name='grouping_incident', to='core.grouping', verbose_name='grouping'),
        ),
        migrations.AddField(
            model_name='groupingincident',
            name='incident',
            field=models.ForeignKey(help_text='Incident which is linked to the grouping', on_delete=django.db.models.deletion.CASCADE, related_name='grouping_incidents', related_query_name='grouping_incident', to='core.incident', verbose_name='incident'),
        ),
        migrations.AddField(
            model_name='groupingalias',
            name='grouping',
            field=models.ForeignKey(help_text='Grouping which is known by this alias', on_delete=django.db.models.deletion.CASCADE, related_name='grouping_aliases', related_query_name='grouping_alias', to='core.grouping', verbose_name='grouping'),
        ),
        migrations.AddField(
            model_name='grouping',
            name='belongs_to_grouping',
            field=models.ForeignKey(blank=True, help_text='The top-level grouping to which this grouping belongs. Leave blank and use grouping relationships if there are more than one relevant top-level groupings.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='groupings', related_query_name='grouping', to='core.grouping', verbose_name='belongs to'),
        ),
        migrations.AddField(
            model_name='grouping',
            name='counties',
            field=models.ManyToManyField(blank=True, db_table='fdp_grouping_county', help_text='Counties in which the grouping operates', related_name='groupings', related_query_name='grouping', to='supporting.County', verbose_name='counties'),
        ),
        migrations.AlterUniqueTogether(
            name='persontitle',
            unique_together={('person', 'title', 'start_year', 'end_year', 'start_month', 'end_month', 'start_day', 'end_day')},
        ),
        migrations.AlterUniqueTogether(
            name='personrelationship',
            unique_together={('subject_person', 'type', 'object_person', 'start_year', 'end_year', 'start_month', 'end_month', 'start_day', 'end_day')},
        ),
        migrations.AlterUniqueTogether(
            name='personpayment',
            unique_together={('person', 'start_year', 'end_year', 'start_month', 'end_month', 'start_day', 'end_day')},
        ),
        migrations.AlterUniqueTogether(
            name='personincident',
            unique_together={('person', 'incident', 'situation_role')},
        ),
        migrations.AlterUniqueTogether(
            name='personidentifier',
            unique_together={('person', 'person_identifier_type', 'identifier')},
        ),
        migrations.AlterUniqueTogether(
            name='persongrouping',
            unique_together={('person', 'grouping', 'type', 'start_year', 'end_year', 'start_month', 'end_month', 'start_day', 'end_day')},
        ),
        migrations.AlterUniqueTogether(
            name='personalias',
            unique_together={('person', 'name')},
        ),
        migrations.AlterUniqueTogether(
            name='groupingrelationship',
            unique_together={('subject_grouping', 'object_grouping', 'type')},
        ),
        migrations.AlterUniqueTogether(
            name='groupingincident',
            unique_together={('grouping', 'incident')},
        ),
        migrations.AlterUniqueTogether(
            name='groupingalias',
            unique_together={('grouping', 'name')},
        ),
        migrations.AlterUniqueTogether(
            name='grouping',
            unique_together={('name', 'code', 'address')},
        ),
    ]
