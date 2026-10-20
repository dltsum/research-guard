"""Regression cases from the real multi-source discovery acceptance failure."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import domain_skill_core as core


class DiscoveryResultContractTests(unittest.TestCase):
    def search(self, skills, repositories, query='research paper audit', limit=3):
        def fetch(url, timeout=30):
            return {'skills': skills} if 'skills.sh' in url else {'items': repositories}
        with patch.object(core, '_json_url', side_effect=fetch):
            return core.discover_domain_skills(query, limit)

    def test_limit_applies_after_combining_sources(self):
        skills=[{'source': 'owner/skills', 'name': f'paper-audit-{i}',
                 'skillId': f'paper-audit-{i}', 'id': f'owner/skills/paper-audit-{i}'} for i in range(3)]
        repos=[{'full_name': f'owner/research-{i}', 'name': f'research-{i}',
                'description': 'paper audit', 'html_url': f'https://github.com/owner/research-{i}'} for i in range(3)]
        result=self.search(skills,repos,limit=3)
        self.assertEqual(len(result['results']),3)
        self.assertEqual(len(result['sources']),2)

    def test_popularity_does_not_admit_unmatched_metadata(self):
        result=self.search([
            {'source':'vendor/cloud','name':'azure-compliance','skillId':'azure-compliance','id':'vendor/cloud/azure-compliance','installs':999999},
            {'source':'owner/skills','name':'research','skillId':'research','id':'owner/skills/research','installs':1},
        ],[{'full_name':'owner/awesome-go','name':'awesome-go','description':'Go frameworks','stars':999999,
             'html_url':'https://github.com/owner/awesome-go'}])
        self.assertEqual([r['name'] for r in result['results']],['research'])
        self.assertEqual(result['results'][0]['matched_query_terms'],['research'])
        self.assertEqual(result['results'][0]['relevance_status'],'METADATA_MATCH_ONLY_NOT_DOMAIN_VALIDATED')

    def test_successful_empty_search_is_not_a_transport_failure(self):
        result=self.search([],[])
        self.assertEqual(result['status'],'NO_RELEVANT_CANDIDATES')
        self.assertTrue(all(s['status']=='PASS' for s in result['sources']))

    def test_all_failed_sources_still_raise(self):
        with patch.object(core,'_json_url',side_effect=core.DomainSkillError('HTTP 503')):
            with self.assertRaises(core.DomainSkillError):
                core.discover_domain_skills('research paper audit',3)

    def test_distinct_skills_in_one_repository_are_retained(self):
        result=self.search([
            {'source':'owner/skills','name':n,'skillId':n,'id':'owner/skills/'+n}
            for n in ['paper-audit','paper-research']
        ],[],limit=3)
        self.assertEqual(len(result['results']),2)

if __name__=='__main__':
    unittest.main()
