import platform

import pytest
import torch
from torch.utils.data.dataloader import DataLoader
from torch.utils.data.dataset import Subset

import tests.base.develop_pipelines as tpipes
from pytorch_lightning import Trainer
from pytorch_lightning.utilities.exceptions import MisconfigurationException
from tests.base import EvalModelTemplate


def test_fit_train_loader_only(tmpdir):

    model = EvalModelTemplate()
    train_dataloader = model.train_dataloader()

    model.train_dataloader = None
    model.val_dataloader = None
    model.test_dataloader = None

    model.validation_step = None
    model.validation_epoch_end = None

    model.test_step = None
    model.test_epoch_end = None

    trainer = Trainer(fast_dev_run=True, default_root_dir=tmpdir)
    trainer.fit(model, train_dataloader=train_dataloader)


def test_fit_val_loader_only(tmpdir):

    model = EvalModelTemplate()
    train_dataloader = model.train_dataloader()
    val_dataloader = model.val_dataloader()

    model.train_dataloader = None
    model.val_dataloader = None
    model.test_dataloader = None

    model.test_step = None
    model.test_epoch_end = None

    trainer = Trainer(fast_dev_run=True, default_root_dir=tmpdir)
    trainer.fit(model, train_dataloader=train_dataloader, val_dataloaders=val_dataloader)


@pytest.mark.parametrize("dataloader_options", [
    dict(val_check_interval=1.1),
    dict(val_check_interval=10000),
])
def test_dataloader_config_errors_runtime(tmpdir, dataloader_options):

    model = EvalModelTemplate()

    trainer = Trainer(
        default_root_dir=tmpdir,
        max_epochs=1,
        **dataloader_options,
    )

    with pytest.raises(ValueError):
        # fit model
        trainer.fit(model)


@pytest.mark.parametrize("dataloader_options", [
    dict(limit_train_batches=-0.1),
    dict(limit_train_batches=1.2),
    dict(limit_val_batches=-0.1),
    dict(limit_val_batches=1.2),
    dict(limit_test_batches=-0.1),
    dict(limit_test_batches=1.2),
])
def test_dataloader_config_errors_init(tmpdir, dataloader_options):
    with pytest.raises(MisconfigurationException):
        Trainer(
            default_root_dir=tmpdir,
            max_epochs=1,
            **dataloader_options,
        )


def test_multiple_val_dataloader(tmpdir):
    """Verify multiple val_dataloader."""

    model = EvalModelTemplate()
    model.val_dataloader = model.val_dataloader__multiple
    model.validation_step = model.validation_step__multiple_dataloaders
    model.validation_epoch_end = model.validation_epoch_end__multiple_dataloaders

    # fit model
    trainer = Trainer(
        default_root_dir=tmpdir,
        max_epochs=1,
        limit_val_batches=0.1,
        limit_train_batches=1.0,
    )
    result = trainer.fit(model)

    # verify training completed
    assert result == 1

    # verify there are 2 val loaders
    assert len(trainer.val_dataloaders) == 2, \
        'Multiple val_dataloaders not initiated properly'

    # make sure predictions are good for each val set
    for dataloader in trainer.val_dataloaders:
        tpipes.run_prediction(dataloader, trainer.model)


@pytest.mark.parametrize('ckpt_path', [None, 'best', 'specific'])
def test_multiple_test_dataloader(tmpdir, ckpt_path):
    """Verify multiple test_dataloader."""

    model_template = EvalModelTemplate()

    class MultipleTestDataloaderModel(EvalModelTemplate):
        def test_dataloader(self):
            return model_template.test_dataloader__multiple()

        def test_step(self, batch, batch_idx, *args, **kwargs):
            return model_template.test_step__multiple_dataloaders(batch, batch_idx, *args, **kwargs)

    model = MultipleTestDataloaderModel()

    # fit model
    trainer = Trainer(
        default_root_dir=tmpdir,
        max_epochs=1,
        limit_val_batches=0.1,
        limit_train_batches=0.2,
    )
    trainer.fit(model)
    if ckpt_path == 'specific':
        ckpt_path = trainer.checkpoint_callback.best_model_path
    trainer.test(ckpt_path=ckpt_path)

    # verify there are 2 test loaders
    assert len(trainer.test_dataloaders) == 2, \
        'Multiple test_dataloaders not initiated properly'

    # make sure predictions are good for each test set
    for dataloader in trainer.test_dataloaders:
        tpipes.run_prediction(dataloader, trainer.model)

    # run the test method
    trainer.test(ckpt_path=ckpt_path)


def test_train_dataloader_passed_to_fit(tmpdir):
    """Verify that train dataloader can be passed to fit """

    # only train passed to fit
    model = EvalModelTemplate()
    trainer = Trainer(
        default_root_dir=tmpdir,
        max_epochs=1,
        limit_val_batches=0.1,
        limit_train_batches=0.2,
    )
    fit_options = dict(train_dataloader=model.dataloader(train=True))
    result = trainer.fit(model, **fit_options)

    assert result == 1


def test_train_val_dataloaders_passed_to_fit(tmpdir):
    """ Verify that train & val dataloader can be passed to fit """

    # train, val passed to fit
    model = EvalModelTemplate()
    trainer = Trainer(
        default_root_dir=tmpdir,
        max_epochs=1,
        limit_val_batches=0.1,
        limit_train_batches=0.2,
    )
    fit_options = dict(train_dataloader=model.dataloader(train=True),
                       val_dataloaders=model.dataloader(train=False))

    result = trainer.fit(model, **fit_options)
    assert result == 1
    assert len(trainer.val_dataloaders) == 1, \
        f'`val_dataloaders` not initiated properly, got {trainer.val_dataloaders}'


@pytest.mark.parametrize('ckpt_path', [None, 'best', 'specific'])
def test_all_dataloaders_passed_to_fit(tmpdir, ckpt_path):
    """Verify train, val & test dataloader(s) can be passed to fit and test method"""

    model = EvalModelTemplate()

    # train, val and test passed to fit
    trainer = Trainer(
        default_root_dir=tmpdir,
        max_epochs=1,
        limit_val_batches=0.1,
        limit_train_batches=0.2,
    )
    fit_options = dict(train_dataloader=model.dataloader(train=True),
                       val_dataloaders=model.dataloader(train=False))
    result = trainer.fit(model, **fit_options)

    if ckpt_path == 'specific':
        ckpt_path = trainer.checkpoint_callback.best_model_path
    test_options = dict(test_dataloaders=model.dataloader(train=False),
                        ckpt_path=ckpt_path)
    trainer.test(**test_options)

    assert result == 1
    assert len(trainer.val_dataloaders) == 1, \
        f'val_dataloaders` not initiated properly, got {trainer.val_dataloaders}'
    assert len(trainer.test_dataloaders) == 1, \
        f'test_dataloaders` not initiated properly, got {trainer.test_dataloaders}'


@pytest.mark.parametrize('ckpt_path', [None, 'best', 'specific'])
def test_multiple_dataloaders_passed_to_fit(tmpdir, ckpt_path):
    """Verify that multiple val & test dataloaders can be passed to fit."""

    model = EvalModelTemplate()
    model.validation_step = model.validation_step__multiple_dataloaders
    model.validation_epoch_end = model.validation_epoch_end__multiple_dataloaders
    model.test_step = model.test_step__multiple_dataloaders

    # train, multiple val and multiple test passed to fit
    trainer = Trainer(
        default_root_dir=tmpdir,
        max_epochs=1,
        limit_val_batches=0.1,
        limit_train_batches=0.2
    )
    fit_options = dict(train_dataloader=model.dataloader(train=True),
                       val_dataloaders=[model.dataloader(train=False),
                                        model.dataloader(train=False)])
    trainer.fit(model, **fit_options)
    if ckpt_path == 'specific':
        ckpt_path = trainer.checkpoint_callback.best_model_path
    test_options = dict(test_dataloaders=[model.dataloader(train=False),
                                          model.dataloader(train=False)],
                        ckpt_path=ckpt_path)
    trainer.test(**test_options)

    assert len(trainer.val_dataloaders) == 2, \
        f'Multiple `val_dataloaders` not initiated properly, got {trainer.val_dataloaders}'
    assert len(trainer.test_dataloaders) == 2, \
        f'Multiple `test_dataloaders` not initiated properly, got {trainer.test_dataloaders}'


@pytest.mark.parametrize(
    ['limit_train_batches', 'limit_val_batches', 'limit_test_batches'],
    [
        pytest.param(0.0, 0.0, 0.0),
        pytest.param(0, 0, 0.5),
        pytest.param(1.0, 1.0, 1.0),
        pytest.param(0.2, 0.4, 0.4),
    ]
)
def test_dataloaders_with_limit_percent_batches(tmpdir, limit_train_batches, limit_val_batches, limit_test_batches):
    """Verify num_batches for val & test dataloaders passed with batch limit in percent"""
    model = EvalModelTemplate()
    model.val_dataloader = model.val_dataloader__multiple_mixed_length
    model.test_dataloader = model.test_dataloader__multiple_mixed_length
    model.validation_step = model.validation_step__multiple_dataloaders
    model.validation_epoch_end = model.validation_epoch_end__multiple_dataloaders
    model.test_step = model.test_step__multiple_dataloaders
    model.test_epoch_end = model.test_epoch_end__multiple_dataloaders

    # train, multiple val and multiple test passed with percent_check
    trainer = Trainer(
        default_root_dir=tmpdir,
        max_epochs=1,
        limit_train_batches=limit_train_batches,
        limit_val_batches=limit_val_batches,
        limit_test_batches=limit_test_batches,
    )
    trainer.fit(model)
    expected_train_batches = int(len(trainer.train_dataloader) * limit_train_batches)
    expected_val_batches = [
        int(len(dataloader) * limit_val_batches) for dataloader in trainer.val_dataloaders
    ]
    assert trainer.num_training_batches == expected_train_batches
    assert trainer.num_val_batches == expected_val_batches

    trainer.test(ckpt_path=None)
    expected_test_batches = [
        int(len(dataloader) * limit_test_batches) for dataloader in trainer.test_dataloaders
    ]
    assert trainer.num_test_batches == expected_test_batches


@pytest.mark.parametrize(
    ['limit_train_batches', 'limit_val_batches', 'limit_test_batches'],
    [
        pytest.param(0, 0, 0),
        pytest.param(1, 2, 3),
        pytest.param(1, 2, 1e50),
    ]
)
def test_dataloaders_with_limit_num_batches(tmpdir, limit_train_batches, limit_val_batches, limit_test_batches):
    """Verify num_batches for val & test dataloaders passed with batch limit as number"""
    model = EvalModelTemplate()
    model.val_dataloader = model.val_dataloader__multiple_mixed_length
    model.test_dataloader = model.test_dataloader__multiple_mixed_length
    model.validation_step = model.validation_step__multiple_dataloaders
    model.validation_epoch_end = model.validation_epoch_end__multiple_dataloaders
    model.test_step = model.test_step__multiple_dataloaders
    model.test_epoch_end = model.test_epoch_end__multiple_dataloaders

    # train, multiple val and multiple test passed with percent_check
    trainer = Trainer(
        default_root_dir=tmpdir,
        max_epochs=1,
        limit_train_batches=limit_train_batches,
        limit_val_batches=limit_val_batches,
        limit_test_batches=limit_test_batches,
    )
    trainer.fit(model)
    assert trainer.num_training_batches == limit_train_batches
    assert trainer.num_val_batches == [limit_val_batches] * len(trainer.val_dataloaders)
    trainer.test(ckpt_path=None)
    assert trainer.num_test_batches == [limit_test_batches] * len(trainer.test_dataloaders)


@pytest.mark.parametrize('ckpt_path', [None, 'best', 'specific'])
def test_mixing_of_dataloader_options(tmpdir, ckpt_path):
    """Verify that dataloaders can be passed to fit"""

    model = EvalModelTemplate()

    trainer_options = dict(
        default_root_dir=tmpdir,
        max_epochs=1,
        limit_val_batches=0.1,
        limit_train_batches=0.2
    )

    # fit model
    trainer = Trainer(**trainer_options)
    results = trainer.fit(model, val_dataloaders=model.dataloader(train=False))
    assert results

    # fit model
    trainer = Trainer(**trainer_options)
    results = trainer.fit(model, val_dataloaders=model.dataloader(train=False))
    assert results
    if ckpt_path == 'specific':
        ckpt_path = trainer.checkpoint_callback.best_model_path
    trainer.test(test_dataloaders=model.dataloader(train=False), ckpt_path=ckpt_path)

    assert len(trainer.val_dataloaders) == 1, \
        f'`val_dataloaders` not initiated properly, got {trainer.val_dataloaders}'
    assert len(trainer.test_dataloaders) == 1, \
        f'`test_dataloaders` not initiated properly, got {trainer.test_dataloaders}'


def test_train_inf_dataloader_error(tmpdir):
    """Test inf train data loader (e.g. IterableDataset)"""
    model = EvalModelTemplate()
    model.train_dataloader = model.train_dataloader__infinite

    trainer = Trainer(default_root_dir=tmpdir, max_epochs=1, val_check_interval=0.5)

    with pytest.raises(MisconfigurationException, match='infinite DataLoader'):
        trainer.fit(model)


def test_val_inf_dataloader_error(tmpdir):
    """Test inf train data loader (e.g. IterableDataset)"""
    model = EvalModelTemplate()
    model.val_dataloader = model.val_dataloader__infinite

    trainer = Trainer(default_root_dir=tmpdir, max_epochs=1, limit_val_batches=0.5)

    with pytest.raises(MisconfigurationException, match='infinite DataLoader'):
        trainer.fit(model)


def test_test_inf_dataloader_error(tmpdir):
    """Test inf train data loader (e.g. IterableDataset)"""
    model = EvalModelTemplate()
    model.test_dataloader = model.test_dataloader__infinite

    trainer = Trainer(default_root_dir=tmpdir, max_epochs=1, limit_test_batches=0.5)

    with pytest.raises(MisconfigurationException, match='infinite DataLoader'):
        trainer.test(model)


@pytest.mark.parametrize('check_interval', [50, 1.0])
def test_inf_train_dataloader(tmpdir, check_interval):
    """Test inf train data loader (e.g. IterableDataset)"""

    model = EvalModelTemplate()
    model.train_dataloader = model.train_dataloader__infinite

    trainer = Trainer(
        default_root_dir=tmpdir,
        max_epochs=1,
        val_check_interval=check_interval,
    )
    result = trainer.fit(model)
    # verify training completed
    assert result == 1


@pytest.mark.parametrize('check_interval', [1.0])
def test_inf_val_dataloader(tmpdir, check_interval):
    """Test inf val data loader (e.g. IterableDataset)"""

    model = EvalModelTemplate()
    model.val_dataloader = model.val_dataloader__infinite

    # logger file to get meta
    trainer = Trainer(
        default_root_dir=tmpdir,
        max_epochs=1,
        val_check_interval=check_interval,
    )
    result = trainer.fit(model)

    # verify training completed
    assert result == 1


def test_error_on_zero_len_dataloader(tmpdir):
    """ Test that error is raised if a zero-length dataloader is defined """

    model = EvalModelTemplate()
    model.train_dataloader = model.train_dataloader__zero_length

    # fit model
    with pytest.raises(ValueError):
        trainer = Trainer(
            default_root_dir=tmpdir,
            max_epochs=1,
            limit_train_batches=0.1,
            limit_val_batches=0.1,
            limit_test_batches=0.1,
        )
        trainer.fit(model)


@pytest.mark.skipif(platform.system() == 'Windows', reason='Does not apply to Windows platform.')
@pytest.mark.parametrize('ckpt_path', [None, 'best', 'specific'])
def test_warning_with_few_workers(tmpdir, ckpt_path):
    """ Test that error is raised if dataloader with only a few workers is used """

    model = EvalModelTemplate()

    # logger file to get meta
    trainer_options = dict(
        default_root_dir=tmpdir,
        max_epochs=1,
        limit_val_batches=0.1,
        limit_train_batches=0.2
    )

    train_dl = model.dataloader(train=True)
    train_dl.num_workers = 0

    val_dl = model.dataloader(train=False)
    val_dl.num_workers = 0

    train_dl = model.dataloader(train=False)
    train_dl.num_workers = 0

    fit_options = dict(train_dataloader=train_dl,
                       val_dataloaders=val_dl)
    trainer = Trainer(**trainer_options)

    # fit model
    with pytest.warns(UserWarning, match='train'):
        trainer.fit(model, **fit_options)

    with pytest.warns(UserWarning, match='val'):
        trainer.fit(model, **fit_options)

    if ckpt_path == 'specific':
        ckpt_path = trainer.checkpoint_callback.best_model_path
    test_options = dict(test_dataloaders=train_dl, ckpt_path=ckpt_path)
    with pytest.warns(UserWarning, match='test'):
        trainer.test(**test_options)


@pytest.mark.skipif(torch.cuda.device_count() < 2, reason='Test requires multiple GPUs')
def test_dataloader_reinit_for_subclass():

    class CustomDataLoader(torch.utils.data.DataLoader):
        def __init__(self, dataset, batch_size=1, shuffle=False, sampler=None,
                     batch_sampler=None, num_workers=0, collate_fn=None,
                     pin_memory=False, drop_last=False, timeout=0,
                     worker_init_fn=None, dummy_kwarg=None):
            super().__init__(dataset, batch_size, shuffle, sampler, batch_sampler,
                             num_workers, collate_fn, pin_memory, drop_last, timeout,
                             worker_init_fn)

            self.dummy_kwarg = dummy_kwarg

    trainer = Trainer(
        gpus=[0, 1],
        num_nodes=1,
        distributed_backend='ddp',
    )

    class CustomDummyObj:
        sampler = None

    result = trainer.auto_add_sampler(CustomDummyObj(), train=True)
    assert isinstance(result, CustomDummyObj), "Wrongly reinstantiated data loader"

    result = trainer.auto_add_sampler(CustomDataLoader(list(range(1000))), train=True)
    assert isinstance(result, torch.utils.data.DataLoader)
    assert isinstance(result, CustomDataLoader)
    assert hasattr(result, 'dummy_kwarg')

    # Shuffled DataLoader should also work
    result = trainer.auto_add_sampler(CustomDataLoader(list(range(1000)), shuffle=True), train=True)
    assert isinstance(result, torch.utils.data.DataLoader)
    assert isinstance(result, CustomDataLoader)
    assert hasattr(result, 'dummy_kwarg')

    class CustomSampler(torch.utils.data.Sampler):
        pass

    # Should raise an error if existing sampler is being replaced
    with pytest.raises(MisconfigurationException, match='DistributedSampler'):
        trainer.auto_add_sampler(
            CustomDataLoader(list(range(1000)), sampler=CustomSampler(list(range(1000)))), train=True)


@pytest.mark.skipif(torch.cuda.device_count() < 3, reason='Test requires multiple GPUs')
def test_batch_size_smaller_than_num_gpus(tmpdir):
    # we need at least 3 gpus for this test
    num_gpus = 3
    batch_size = 3

    class CurrentTestModel(EvalModelTemplate):

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # batch norm doesn't work with batch size 1, we replace it
            self.c_d1_bn = torch.nn.ReLU()

        def training_step(self, *args, **kwargs):
            output = super().training_step(*args, **kwargs)
            loss = output['loss']
            # we make sure to add some metrics to the output dict,
            # this is essential for this test
            output['progress_bar'] = {'train_loss': loss}
            return output

        def train_dataloader(self):
            dataloader = super().train_dataloader()
            # construct a dataset with a size that is not divisible by num_gpus
            # therefore the last batch will have a size < num_gpus
            size = num_gpus * batch_size + (num_gpus - 1)
            dataset = Subset(dataloader.dataset, range(size))
            dataloader = DataLoader(
                dataset,
                batch_size=self.batch_size,
                drop_last=False,
            )
            return dataloader

    hparams = EvalModelTemplate.get_default_hparams()
    hparams['batch_size'] = batch_size
    model = CurrentTestModel(**hparams)

    trainer = Trainer(
        default_root_dir=tmpdir,
        max_epochs=1,
        limit_train_batches=0.1,
        limit_val_batches=0,
        gpus=num_gpus,
    )

    # we expect the reduction for the metrics also to happen on the last batch
    # where we will get fewer metrics than gpus
    result = trainer.fit(model)
    assert 1 == result


@pytest.mark.parametrize('check_interval', [1.0])
def test_val_dataloader_not_implemented_error(tmpdir, check_interval):
    """Test not_implemented_error data loader (e.g. IterableDataset)"""

    model = EvalModelTemplate()
    model.val_dataloader = model.val_dataloader__not_implemented_error

    # logger file to get meta
    trainer = Trainer(
        default_root_dir=tmpdir,
        max_steps=5,
        max_epochs=1,
        val_check_interval=check_interval,
    )
    result = trainer.fit(model)
    # verify training completed
    assert result == 1


@pytest.mark.parametrize('check_interval', [50, 1.0])
def test_train_dataloader_not_implemented_error(tmpdir, check_interval):
    """Test not_implemented_error train data loader (e.g. IterableDataset)"""

    model = EvalModelTemplate()
    model.train_dataloader = model.train_dataloader__not_implemented_error
    model.val_dataloader = model.val_dataloader__not_implemented_error

    trainer = Trainer(
        default_root_dir=tmpdir,
        max_steps=5,
        max_epochs=1,
        val_check_interval=check_interval
    )
    result = trainer.fit(model)
    # verify training completed
    assert result == 1


def test_train_dataloader_not_implemented_error_failed(tmpdir):
    """Test not_implemented_error train data loader (e.g. IterableDataset)"""
    model = EvalModelTemplate()
    model.train_dataloader = model.train_dataloader__not_implemented_error

    trainer = Trainer(default_root_dir=tmpdir, max_steps=5, max_epochs=1, val_check_interval=0.5)

    with pytest.raises(MisconfigurationException, match='infinite DataLoader'):
        trainer.fit(model)


def test_val_dataloader_not_implemented_error_failed(tmpdir):
    """Test not_implemented_error train data loader (e.g. IterableDataset)"""
    model = EvalModelTemplate()
    model.val_dataloader = model.val_dataloader__not_implemented_error

    trainer = Trainer(default_root_dir=tmpdir, max_steps=5, max_epochs=1, limit_val_batches=0.5)

    with pytest.raises(MisconfigurationException, match='infinite DataLoader'):
        trainer.fit(model)


def test_test_dataloader_not_implemented_error_failed(tmpdir):
    """Test not_implemented_error train data loader (e.g. IterableDataset)"""
    model = EvalModelTemplate()
    model.test_dataloader = model.test_dataloader__not_implemented_error

    trainer = Trainer(default_root_dir=tmpdir, max_steps=5, max_epochs=1, limit_test_batches=0.5)

    with pytest.raises(MisconfigurationException, match='infinite DataLoader'):
        trainer.test(model)
