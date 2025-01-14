import unittest
import pandas as pd
from ebk.streamlit.filters import sanitize_dataframe

class TestFilters(unittest.TestCase):
    def test_sanitize_dataframe(self):
        data = {
            'title': ['Book One', 'Book Two'],
            'creators': [['Author A'], 'Author B'],  # Mixed types
            'subjects': ['Subject X', ['Subject Y', 'Subject Z']],
            'file_paths': [['path1.pdf'], 'path2.epub'],
            'identifiers': [{'ISBN': '12345'}, 'invalid'],
            'language': ['en', None],
            'cover_path': ['cover1.jpg', 123]
        }
        df = pd.DataFrame(data)
        sanitized_df = sanitize_dataframe(df)
        
        self.assertEqual(sanitized_df['creators'][1], ['Author B'])
        self.assertEqual(sanitized_df['subjects'][0], [])
        self.assertEqual(sanitized_df['file_paths'][1], ['path2.epub'])
        self.assertEqual(sanitized_df['identifiers'][1], {})
        self.assertEqual(sanitized_df['language'][1], '')
        self.assertEqual(sanitized_df['cover_path'][1], '')
