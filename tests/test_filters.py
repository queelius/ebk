import unittest
import sys
from pathlib import Path

# Skip this test file if the streamlit integration is not available
# since it's been moved to integrations/
try:
    # Add integrations path to sys.path temporarily
    integrations_path = Path(__file__).parent.parent / "integrations" / "streamlit-dashboard"
    sys.path.insert(0, str(integrations_path))
    from filters import sanitize_dataframe
    import pandas as pd
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False

@unittest.skipUnless(STREAMLIT_AVAILABLE, "Streamlit integration not available")
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
        self.assertEqual(sanitized_df['subjects'][0], ['Subject X'])  # String should be wrapped in list
        self.assertEqual(sanitized_df['file_paths'][1], ['path2.epub'])
        self.assertEqual(sanitized_df['identifiers'][1], {})
        self.assertEqual(sanitized_df['language'][1], '')
        self.assertEqual(sanitized_df['cover_path'][1], '')
