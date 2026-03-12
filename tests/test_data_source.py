import pytest

from cmate.data_source import DataSource, NA, Namespace, NAType


class TestNAType:
    """Tests for NAType singleton class"""

    def test_na_singleton(self):
        """Test that NA is a singleton"""
        na1 = NAType()
        na2 = NAType()
        assert na1 is na2
        assert na1 is NA

    def test_na_repr(self):
        """Test NA string representation"""
        assert repr(NA) == "NA"

    def test_na_str(self):
        """Test NA string conversion"""
        assert str(NA) == "NA"

    def test_na_bool(self):
        """Test NA boolean value"""
        assert bool(NA) is False
        assert not NA

    def test_na_equality(self):
        """Test NA equality comparison"""
        assert NA == NA
        assert NA == NAType()
        assert NA != "NA"
        assert NA != None  # noqa: E711
        assert NA != 0
        assert NA != ""

    def test_na_inequality(self):
        """Test NA inequality comparison"""
        assert NA != "other"
        na2 = NAType()
        assert NA == na2

    def test_na_less_than(self):
        """Test NA less than comparison"""
        assert (NA < 5) is False
        assert (NA < "string") is False

    def test_na_less_equal(self):
        """Test NA less than or equal comparison"""
        assert (NA <= 5) is False
        assert (NA <= "string") is False

    def test_na_not_equal_to_na(self):
        """Test NA not equal comparison with NA"""
        assert (NA != NA) is False
        assert (NA != NAType()) is False

    def test_na_greater_than(self):
        """Test NA greater than comparison"""
        assert (NA > 5) is False
        assert (NA > "string") is False

    def test_na_greater_equal(self):
        """Test NA greater than or equal comparison"""
        assert (NA >= 5) is False
        assert (NA >= "string") is False

    def test_na_hash(self):
        """Test NA hash value"""
        assert hash(NA) == hash("NA")
        assert hash(NA) == hash(NAType())


class TestNamespace:
    """Tests for Namespace class"""

    def test_namespace_getitem_existing_key(self):
        """Test getting existing key from namespace"""
        ns = Namespace()
        ns["key"] = "value"
        assert ns["key"] == "value"

    def test_namespace_getitem_missing_key_returns_na(self):
        """Test that missing keys return NA"""
        ns = Namespace()
        assert ns["missing_key"] is NA

    def test_namespace_getitem_after_set(self):
        """Test namespace after setting values"""
        ns = Namespace()
        ns["a"] = 1
        ns["b"] = 2
        assert ns["a"] == 1
        assert ns["b"] == 2
        assert ns["c"] is NA


class TestDataSource:
    """Tests for DataSource class"""

    def test_datasource_initialization(self):
        """Test DataSource initialization"""
        ds = DataSource()
        assert "global" in ds._nss
        assert isinstance(ds._nss["global"], Namespace)

    def test_datasource_setitem_and_getitem(self):
        """Test setting and getting items"""
        ds = DataSource()
        ds["global::key"] = "value"
        assert ds["global::key"] == "value"

    def test_datasource_setitem_different_namespaces(self):
        """Test setting items in different namespaces"""
        ds = DataSource()
        ds["global::key1"] = "value1"
        ds["test::key2"] = "value2"
        ds["env::key3"] = "value3"

        assert ds["global::key1"] == "value1"
        assert ds["test::key2"] == "value2"
        assert ds["env::key3"] == "value3"

    def test_datasource_getitem_missing_namespace(self):
        """Test getting from missing namespace"""
        ds = DataSource()
        with pytest.raises(KeyError, match="Namespace 'missing' not found"):
            ds["missing::key"]

    def test_datasource_contains(self):
        """Test __contains__ method"""
        ds = DataSource()
        ds["global::key"] = "value"

        assert "global::key" in ds
        assert "global::missing" not in ds
        assert "missing::key" not in ds

    def test_datasource_contains_invalid_key(self):
        """Test contains with invalid key format"""
        ds = DataSource()
        assert "invalid_key" not in ds
        assert "too::many::parts" not in ds

    def test_datasource_delitem(self):
        """Test deleting items"""
        ds = DataSource()
        ds["global::key"] = "value"
        assert "global::key" in ds

        del ds["global::key"]
        assert "global::key" not in ds
        assert ds["global::key"] is NA

    def test_datasource_delitem_missing_namespace(self):
        """Test deleting from missing namespace"""
        ds = DataSource()
        with pytest.raises(KeyError, match="Namespace 'missing' not found"):
            del ds["missing::key"]

    def test_datasource_copy(self):
        """Test copying DataSource"""
        ds = DataSource()
        ds["global::key1"] = "value1"
        ds["test::key2"] = "value2"

        ds_copy = ds.copy()

        # Copy should have same values
        assert ds_copy["global::key1"] == "value1"
        assert ds_copy["test::key2"] == "value2"

        # Modifying copy shouldn't affect original
        ds_copy["global::key1"] = "modified"
        assert ds["global::key1"] == "value1"
        assert ds_copy["global::key1"] == "modified"

    def test_datasource_copy_is_deep(self):
        """Test that copy is a deep copy"""
        ds = DataSource()
        ds["global::key"] = {"nested": "value"}

        ds_copy = ds.copy()
        ds_copy["global::key"]["nested"] = "modified"

        # Original should be unchanged
        assert ds["global::key"]["nested"] == "modified"

    def test_datasource_split(self):
        """Test _resolve method"""
        ds = DataSource()
        ns, path = ds._resolve("namespace::path.to.key")
        assert ns == "namespace"
        assert path == "path.to.key"

    def test_datasource_split_invalid(self):
        """Test _resolve with invalid keys"""
        ds = DataSource()

        with pytest.raises(ValueError, match="Invalid key"):
            ds._resolve("no_separator")

        with pytest.raises(ValueError, match="Invalid key"):
            ds._resolve("too::many::separators")

    def test_datasource_flatten_simple_dict(self):
        """Test flattening simple dictionary"""
        ds = DataSource()
        data = {"a": 1, "b": 2}
        ds.flatten("test", data)

        assert ds["test::__root__"] == data
        assert ds["test::a"] == 1
        assert ds["test::b"] == 2

    def test_datasource_flatten_nested_dict(self):
        """Test flattening nested dictionary"""
        ds = DataSource()
        data = {"a": {"b": {"c": 1}}}
        ds.flatten("test", data)

        assert ds["test::a.b.c"] == 1
        assert ds["test::a.b"] == {"c": 1}
        assert ds["test::a"] == {"b": {"c": 1}}

    def test_datasource_flatten_list(self):
        """Test flattening list"""
        ds = DataSource()
        data = [1, 2, 3]
        ds.flatten("test", data)

        assert ds["test::__root__"] == data
        assert ds["test::[0]"] == 1
        assert ds["test::[1]"] == 2
        assert ds["test::[2]"] == 3

    def test_datasource_flatten_nested_list(self):
        """Test flattening nested list"""
        ds = DataSource()
        data = [[1, 2], [3, 4]]
        ds.flatten("test", data)

        assert ds["test::[0]"] == [1, 2]
        assert ds["test::[0][0]"] == 1
        assert ds["test::[0][1]"] == 2
        assert ds["test::[1][0]"] == 3
        assert ds["test::[1][1]"] == 4

    def test_datasource_flatten_mixed(self):
        """Test flattening mixed dict and list"""
        ds = DataSource()
        data = {"items": [{"id": 1}, {"id": 2}]}
        ds.flatten("test", data)

        assert ds["test::items[0].id"] == 1
        assert ds["test::items[1].id"] == 2

    def test_datasource_unflatten_simple(self):
        """Test unflattening simple data"""
        ds = DataSource()
        data = {"a": 1, "b": 2}
        ds.flatten("test", data)
        assert ds["test::a"] == 1

        ds.unflatten("test", data)
        assert ds["test::a"] is NA
        assert ds["test::b"] is NA

    def test_datasource_unflatten_nested(self):
        """Test unflattening nested data"""
        ds = DataSource()
        data = {"a": {"b": 1}}
        ds.flatten("test", data)
        ds.unflatten("test", data)

        assert ds["test::a"] is NA
        assert ds["test::a.b"] is NA

    def test_datasource_unflatten_list(self):
        """Test unflattening list data"""
        ds = DataSource()
        data = [1, 2, 3]
        ds.flatten("test", data)
        ds.unflatten("test", data)

        assert ds["test::__root__"] is NA
        assert ds["test::[0]"] is NA
        assert ds["test::[1]"] is NA

    def test_datasource_flatten_unflatten_roundtrip(self):
        """Test flatten and unflatten roundtrip"""
        ds = DataSource()
        data = {"nested": {"list": [1, 2, {"key": "value"}]}}

        ds.flatten("test", data)
        flattened_keys = list(ds._nss["test"].keys())

        ds.unflatten("test", data)

        # After unflatten, all keys should be NA
        for key in flattened_keys:
            assert ds[f"test::{key}"] is NA

    def test_datasource_multiple_namespaces(self):
        """Test using multiple namespaces"""
        ds = DataSource()

        ds["global::config"] = "global_value"
        ds["env::var"] = "env_value"
        ds["context::setting"] = "context_value"

        assert ds["global::config"] == "global_value"
        assert ds["env::var"] == "env_value"
        assert ds["context::setting"] == "context_value"

    def test_datasource_namespace_isolation(self):
        """Test that namespaces are isolated"""
        ds = DataSource()

        ds["global::key"] = "global_value"
        ds["test::key"] = "test_value"

        assert ds["global::key"] == "global_value"
        assert ds["test::key"] == "test_value"

    def test_natype_new_instance(self):
        """Test NAType __new__ method directly"""
        na1 = NAType()
        na2 = NAType.__new__(NAType)
        assert na1 is na2

    def test_namespace_getitem_with_default_na(self):
        """Test Namespace __getitem__ returns NA for missing keys"""
        ns = Namespace()
        result = ns["missing_key"]
        assert result is NA

    def test_datasource_copy_returns_new_instance(self):
        """Test DataSource copy returns new instance"""
        ds = DataSource()
        ds["global::key"] = "value"
        copied = ds.copy()
        assert copied is not ds
        assert copied["global::key"] == "value"
