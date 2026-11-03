"""
Auto-generated from the user's notebook (전처리.ipynb).
Only function/class definitions were extracted to avoid side effects.
If some needed functions are missing, feel free to edit this file directly.
"""

def get_bbox_coords(x_list, y_list):
    xmin, xmax = min(x_list), max(x_list)
    ymin, ymax = min(y_list), max(y_list)
    return xmin, ymin, xmax, ymax

# 함수: 파일명에 사용 불가능한 문자 제거
def sanitize_filename(name):
    return "".join(c for c in name if c.isalnum() or c in ('_', '-', '.', '(', ')')).rstrip()

# 단어별 bbox 잘라 저장
def get_bbox_coords(x_list, y_list):
    return min(x_list), min(y_list), max(x_list), max(y_list)

def sanitize_filename(name):
    return "".join(c for c in name if c.isalnum() or c in ('_', '-', '.', '(', ')')).rstrip()

def find_image_path(img_name):
    for dir_path in image_root_dirs:
        full_path = os.path.join(dir_path, img_name)
        if os.path.exists(full_path):
            return full_path
    return None

# 전처리 시작
class SiameseDataset(Dataset):
    def __init__(self, csv_path, transform=None):
        self.data = pd.read_csv(csv_path)
        self.transform = transform if transform else transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor()
        ])

    def __getitem__(self, index):
        row = self.data.iloc[index]
        img1_path = row['img1']
        img2_path = row['img2']
        label = torch.tensor(row['label'], dtype=torch.float32)

        img1 = Image.open(img1_path).convert("RGB")
        img2 = Image.open(img2_path).convert("RGB")

        img1 = self.transform(img1)
        img2 = self.transform(img2)

        return img1, img2, label

    def __len__(self):
        return len(self.data)
class SiameseNetwork(nn.Module):
    def __init__(self):
        super(SiameseNetwork, self).__init__()
        # 사전 학습된 ResNet18을 가져오고 마지막 FC층 제거
        resnet = models.resnet18(pretrained=True)
        modules = list(resnet.children())[:-1]  # 마지막 FC 레이어 제거
        self.feature_extractor = nn.Sequential(*modules)

        # 임베딩 벡터 차원: 512
        self.embedding_dim = 512

        # 두 벡터 간 차이로부터 최종 예측값 출력하는 분류기
        self.classifier = nn.Sequential(
            nn.Linear(self.embedding_dim, 256),
            nn.ReLU(),
            nn.Linear(256, 1),
            nn.Sigmoid()  # BCE Loss를 쓰므로 Sigmoid
        )

    def forward_once(self, x):
        x = self.feature_extractor(x)
        x = x.view(x.size(0), -1)  # Flatten
        return x

    def forward(self, img1, img2):
        emb1 = self.forward_once(img1)
        emb2 = self.forward_once(img2)
        diff = torch.abs(emb1 - emb2)  # 절댓값 차이 (L1 distance)
        out = self.classifier(diff)
        return out
def get_bbox_coords(x_list, y_list):
    return min(x_list), min(y_list), max(x_list), max(y_list)

def sanitize_filename(name):
    return "".join(c for c in name if c.isalnum() or c in ('_', '-', '.', '(', ')')).rstrip()

# ✅ 각 subfolder 별로 반복 처리
